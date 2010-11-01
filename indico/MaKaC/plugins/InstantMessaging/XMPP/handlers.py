# -*- coding: utf-8 -*-
##
## $id$
##
## This file is part of CDS Indico.
## Copyright (C) 2002, 2003, 2004, 2005, 2006, 2007 CERN.
##
## CDS Indico is free software; you can redistribute it and/or
## modify it under the terms of the GNU General Public License as
## published by the Free Software Foundation; either version 2 of the
## License, or (at your option) any later version.
##
## CDS Indico is distributed in the hope that it will be useful, but
## WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
## General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with CDS Indico; if not, write to the Free Software Foundation, Inc.,
## 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

from MaKaC.plugins.InstantMessaging.Chatroom import XMPPChatroom
from MaKaC.plugins.InstantMessaging.handlers import ChatroomBase
from MaKaC.services.implementation.base import ServiceBase, ParameterManager
from MaKaC.services.interface.rpc.common import ServiceError, NoReportError
from MaKaC.common.contextManager import ContextManager
from MaKaC.common.logger import Logger
from MaKaC.common.externalOperationsManager import ExternalOperationsManager
from MaKaC.common.timezoneUtils import nowutc, DisplayTZ
from MaKaC.common.fossilize import fossilize
from MaKaC.plugins import Observable
from MaKaC.plugins.util import PluginFieldsWrapper
from MaKaC.plugins.helpers import DBHelpers, MailHelper

from MaKaC.plugins.InstantMessaging.XMPP.bot import IndicoXMPPBotRoomExists, IndicoXMPPBotCreateRoom, IndicoXMPPBotEditRoom, IndicoXMPPBotDeleteRoom, IndicoXMPPBotGetPreferences
from MaKaC.conference import ConferenceHolder


class XMPPChatroomService( ChatroomBase ):

    messages = { 'default': _('There was an error while connecting to the XMPP server'),\
                 'sameId': _('There is already a chat room with the same id'), \
                 'sameName': _('There is already a chat room in the server with that name, please choose another one'), \
                 'creating': _('There was an error while creating the chat room in the local server. Please try again later'), \
                 'editing': _('There was an error while editing the chat room in the local server. Please try again later'), \
                 'deleting': _('There was an error while deleting the chat room in the XMPP server. Please try to do it manually from your client' \
                               ' or contact the administrators'), \
                 'connecting': _('There was an error while connecting to the XMPP server. Maybe the username or password are not correct'), \
                 'CRdeletedFromClient': _('Someone deleted the chat room from the XMPP server since this page was loaded. We recommend you to delete the chatroom from Indico as well')
                 }

    def __init__(self, params, remoteHost, session):
        ChatroomBase.__init__(self, params, remoteHost, session)
        #we want the data from the XMPP plugin in the InstantMessaging Plugin type
        oh = PluginFieldsWrapper('InstantMessaging', 'XMPP')
        self._botJID = oh.getOption('indicoUsername') + '@' + oh.getOption('chatServerHost')
        self._botPass = oh.getOption('indicoPassword')

    def _checkParams(self):
        ChatroomBase._checkParams(self)
        pm = ParameterManager(self._params.get('chatroomParams'))

        self._description = pm.extract('description', pType=str, allowEmpty = True)
        if self._createdInLocalServer:
            oh = PluginFieldsWrapper('InstantMessaging', 'XMPP')
            self._host = oh.getOption('chatServerHost')
        else:
            self._host = pm.extract('host', pType=str, allowEmpty = False)

        self._password = pm.extract('roomPass', pType=str, allowEmpty = True, defaultValue='')
        self._showPass = pm.extract('showPass', pType=bool, allowEmpty = True)

        self._user = self._getUser()

    def proccessAnswer(self, answer):
        # controlled error
        if hasattr(answer, '_error') and answer._error['error']:
            # we need to make a distinction in this case to show the widget in the client
            if answer._error['reason'] is 'roomExists':
                Logger.get('InstantMessaging (XMPP-XMPP server)').error("User %s tried to create the room %s, but it exists already" %(self._room.getOwner(), self._room.getTitle()))
                raise NoReportError(self.messages['sameName'], explanation='roomExists')
            else:
                Logger.get('InstantMessaging (XMPP-XMPP server)').error("User %s executed an XMPP operation that provoked an error: %s" %(self._room.getOwner(), answer._error['reason']))
                raise ServiceError(message = answer._error['reason'])
        # this should never happen! When an error happens, it should ALWAYS be set in the
        # _error variable in bot.py
        elif not hasattr(answer, '_error'):
            Logger.get('InstantMessaging (XMPP-XMPP server)').error("Really unexpected error, no _error attribute was found. Please check this. User: %s. Chat room ID: %s" %(self._room.getOwner(), self._room.getId()))
            raise ServiceError(message = self.messages['connecting'])
        return True

    def roomExistsXMPP(self, jid, password, room):
        """ Creates the room in the XMPP server """
        try:
            self._bot = IndicoXMPPBotRoomExists(jid, password, room)
            #make operation atomic
            ExternalOperationsManager.execute(self._bot, "roomExistsXMPP", self._bot.run)
        except Exception, e:
            Logger.get('InstantMessaging (XMPP-XMPP server)').exception("Exception while checking if room existed")
            raise ServiceError(message = self.messages['default'])
        return self.proccessAnswer(self._bot)

    def roomPreferencesXMPP(self, jid, password, room):
        """ Creates the room in the XMPP server """
        try:
            self._bot = IndicoXMPPBotGetPreferences(self._botJID, self._botPass, self._room)
            #make operation atomic
            ExternalOperationsManager.execute(self._bot, "roomPreferencesXMPP", self._bot.run)
        except Exception, e:
            Logger.get('InstantMessaging (XMPP-XMPP server)').error("Exception while checking if room existed: %s" %e)
            raise ServiceError(message = self.messages['default'])
        return self.proccessAnswer(self._bot)

    def createRoomXMPP(self, jid, password, room):
        """ Creates the room in the XMPP server """
        try:
            self._bot = IndicoXMPPBotCreateRoom(jid, password, room)
            #make operation atomic
            ExternalOperationsManager.execute(self._bot, "createRoomXMPP", self._bot.run)
        except Exception, e:
            Logger.get('InstantMessaging (XMPP-XMPP server)').error("Exception while creating: %s" %e)
            raise ServiceError(message = self.messages['creating'])
        return self.proccessAnswer(self._bot)

    def editRoomXMPP(self, jid, password, room, checkRoomExists = True):
        """ Edits the room in the XMPP server. If checkRoomExists is set to true
            it means that we are changing the chat room name and we want to know if the new
            name is already taken in the server. If it's false it means that we only want to change
            some of the parameters in the room, so no need to check the name. """
        try:
            self._bot = IndicoXMPPBotEditRoom(jid, password, room, checkRoomExists)
            #make operation atomic
            ExternalOperationsManager.execute(self._bot, "editRoomXMPP", self._bot.run)
        except Exception, e:
            Logger.get('InstantMessaging (XMPP-XMPP server)').error("Exception while editing: %s" %e)
            raise ServiceError(message = self.messages['editing'])
        return self.proccessAnswer(self._bot)

    def deleteRoomXMPP(self, jid, password, room, message):
        """ Deletes the room in the XMPP server """
        try:
            self._bot = IndicoXMPPBotDeleteRoom(jid, password, room, message)
            #make operation atomic
            ExternalOperationsManager.execute(self._bot, "deleteRoomXMPP", self._bot.run)
        except Exception, e:
            Logger.get('InstantMessaging (XMPP-XMPP server)').error("Exception while deleting: %s" %e)
            raise ServiceError(message = self.messages['deleting'])
        return self.proccessAnswer(self._bot)

    def _executeExternalOperation(self, bot, operName, messageName):
        """ we need the instance of the XMPP operation we're going to do, and also its name.
            Finally, we'll need the name of the error message to show in case something happens"""


class CreateChatroom( XMPPChatroomService ):

    def __init__(self, params, remoteHost, session):
        XMPPChatroomService.__init__(self, params, remoteHost, session)

    def _checkParams(self):
        XMPPChatroomService._checkParams(self)
        self._user = self._getUser()

    def _getAnswer( self ):
        self._room = XMPPChatroom(self._title, \
                              self._user, \
                              ConferenceHolder().getById(self._conferenceID), \
                              None, \
                              self._description, \
                              self._createdInLocalServer, \
                              self._host, \
                              self._password, \
                              self._showRoom, \
                              self._showPass)

        if self._room.getCreatedInLocalServer():
            self.roomExistsXMPP(self._botJID, self._botPass, self._room)
        try:
            ContextManager.getdefault('mailHelper', MailHelper())
            self._notify('createChatroom', {'room': self._room})
        except ServiceError, e:
            Logger.get('InstantMessaging (XMPP-Indico server)').error("Exception while notifying observers: %s" %e)
            raise ServiceError( message=self.messages['sameId']+e )
        except NoReportError, e:
            Logger.get('InstantMessaging (XMPP-Indico server)').error("Room exists: %s" %e)
            raise NoReportError(self.messages['sameName'], explanation='roomExists')
        except Exception, e:
            Logger.get('InstantMessaging (XMPP-Indico server)').error("Weird exception while notifying observers: %s" %e)
            raise ServiceError( message=str(e) )
        if self._room.getCreatedInLocalServer():
            #if we're not creating the room in our server we don't need to call the bot
            self.createRoomXMPP(self._botJID, self._botPass, self._room)

        Logger.get('InstantMessaging (XMPP-Indico server)').info("The room %s has been created by the user %s at %s hours" %(self._title, self._user.getName(), self._room.getModificationDate()))

        tz = DisplayTZ(self._aw, self._room.getConference()).getDisplayTZ()

        ContextManager.get('mailHelper').sendMails()
        return self._room.fossilize(tz=tz)



class EditChatroom( XMPPChatroomService ):

    def __init__(self, params, remoteHost, session):
        XMPPChatroomService.__init__(self, params, remoteHost, session)

    def _checkParams(self):
        XMPPChatroomService._checkParams(self)

        pm = ParameterManager(self._params.get('chatroomParams'))
        self._id = pm.extract('id', pType=str, allowEmpty = False)
        self._user = self._getUser()
        self._modificationDate = nowutc()

    def _getAnswer( self ):
        values = {'title':self._title, \
                  'user':self._user, \
                  'modificationDate':self._modificationDate, \
                  'description':self._description, \
                  'createdInLocalServer':self._createdInLocalServer, \
                  'host':self._host, \
                  'password':self._password, \
                  'showRoom':self._showRoom, \
                  'showPass':self._showPass, \
                  'conference':ConferenceHolder().getById(self._conferenceID) \
                  }

        try:
            self._room = DBHelpers().getChatroom(self._id)
            oldRoom = XMPPChatroom(self._room.getTitle(), self._room.getOwner(), ConferenceHolder().getById(self._conferenceID), createdInLocalServer = self._room.getCreatedInLocalServer())
            self._room.setValues(values)

            conditions = {'titleChanged': oldRoom.getTitle() != self._room.getTitle(), \
                          'XMPPServerNotChanged': oldRoom.getCreatedInLocalServer() and self._room.getCreatedInLocalServer(), \
                          'XMPPServerChanged2External': oldRoom.getCreatedInLocalServer() and not self._room.getCreatedInLocalServer(), \
                          'XMPPServerChanged2Local': not oldRoom.getCreatedInLocalServer() and self._room.getCreatedInLocalServer() \
                         }

            if conditions['titleChanged'] and conditions['XMPPServerNotChanged'] or conditions['XMPPServerChanged2Local']:
                self.roomExistsXMPP(self._botJID, self._botPass, self._room)

            #edit the chat room in indico
            ContextManager.getdefault('mailHelper', MailHelper())
            self._notify('editChatroom', {'oldTitle': oldRoom.getTitle(), 'newRoom':self._room})
        except ServiceError, e:
            Logger.get('InstantMessaging (XMPP-Indico server)').error("Exception while editing: %s" %e)
            raise ServiceError( message=_('Problem while accessing the database: %s' %e))
        except Exception, e:
            Logger.get('InstantMessaging (XMPP-Indico server)').error("Weird exception while notifying observers: %s" %e)
            raise NoReportError( self.messages['editing'], explanation='roomExists')

        #edit the chat room in XMPP
        modified = False
        if conditions['titleChanged'] and conditions['XMPPServerNotChanged']:
            #before, the chat room was in the XMPP server. After editing, it is still in the XMPP server, but the title has changed.
            #This means that we'll have to delete the old room and create the new one with the new title
            message = "%s has requested to delete this room. The new chat room name is %s, please reconnect there" %(self._user.getName(), self._title)
            modified = self.deleteRoomXMPP(self._botJID, self._botPass, oldRoom, message)
            modified = self.createRoomXMPP(self._botJID, self._botPass, self._room)

        else:
            #before, the room had to be created in the XMPP server, after the modification a different server will be used
            if conditions['XMPPServerChanged2External']:
                #delete the existing room in the XMPP server
                message = "%s has requested to delete this room. The host for the new chat room is %s, please reconnect there" %(self._user.getName(), self._host)
                modified = self.deleteRoomXMPP(self._botJID, self._botPass, oldRoom, message)

            #before, the room was in an external server, now it's in the XMPP server
            elif conditions['XMPPServerChanged2Local']:
                #create the room in the XMPP server
                modified = self.createRoomXMPP(self._botJID, self._botPass, self._room)

            #no changes were made in this area, we edit the room in case it's created in the XMPP server
            elif self._room.getCreatedInLocalServer():
                modified = self.editRoomXMPP(self._botJID, self._botPass, self._room, False)

        if modified:
            Logger.get('InstantMessaging (XMPP-Indico server)').info("The room %s has been modified by the user %s at %s hours" %(self._title, self._user.getName(), self._room.getModificationDate()))

        ContextManager.get('mailHelper').sendMails()
        return self._room.fossilizeMultiConference(values['conference'])



class DeleteChatroom( XMPPChatroomService ):

    def __init__(self, params, remoteHost, session):
        XMPPChatroomService.__init__(self, params, remoteHost, session)

    def _checkParams(self):
        XMPPChatroomService._checkParams(self)
        pm = ParameterManager(self._params.get('chatroomParams'))
        self._id = pm.extract('id', pType=str, allowEmpty = False)
        self._room = DBHelpers().getChatroom(self._id)
        self._user = self._getUser()

    def _getAnswer( self ):
        message = _("%s has requested to delete this room. Please address this person for further information" %self._user.getName())
        #delete room from Indico
        try:
            ContextManager.getdefault('mailHelper', MailHelper())
            self._notify('deleteChatroom', {'room': self._room})
        except ServiceError, e:
            Logger.get('InstantMessaging (XMPP-Indico server)').error(message=_('Problem deleting indexes in the database for chat room %s: %s' %(self._room.getTitle(), e)))
            raise ServiceError( message=_('Problem deleting indexes in the database for chat room %s: %s' %(self._room.getTitle(), e)))

        #delete room from our XMPP server (if neccesary)
        if self._room.getCreatedInLocalServer() and len(self._room.getConferences()) is 0:
            self.deleteRoomXMPP(self._botJID, self._botPass, self._room, message)

        Logger.get('InstantMessaging (XMPP-Indico server)').info("The room %s has been deleted by the user %s at %s hours" %(self._title, self._user.getName(), nowutc()))

        ContextManager.get('mailHelper').sendMails()
        return True


class GetRoomPreferences( XMPPChatroomService ):

    def __init__(self, params, remoteHost, session):
        XMPPChatroomService.__init__(self, params, remoteHost, session)

    def _checkParams(self):
        XMPPChatroomService._checkParams(self)
        pm = ParameterManager(self._params.get('chatroomParams'))
        self._id = pm.extract('id', pType=str, allowEmpty = False)
        self._user = self._getUser()

    def _getAnswer( self ):
        fieldsToCheck = {'muc#roomconfig_roomdesc': 'Description', \
                         'muc#roomconfig_roomsecret': 'Password'
                        }

        try:
            self._room = DBHelpers().getChatroom(self._id)
        except Exception, e:
            raise ServiceError( message=_('Error trying to get the chat room preferences: %s')%e)

        # this method will fill the self._bot._form attr
        self.roomPreferencesXMPP(self._botJID, self._botPass, self._room)

        #get the preferences and check updates
        for preference in self._bot._form.fields:
            if preference.var in fieldsToCheck.keys():
                #we execute setDescription or setPassword with the new value
                getattr(self._room, 'set'+ fieldsToCheck[preference.var])(preference.value.pop())

        return self._room.fossilize()


class GetRoomsByUser( ServiceBase ):

    def __init__(self, params, remoteHost, session):
        ServiceBase.__init__(self, params, remoteHost, session)

    def _checkParams(self):
        self._user = self._params['usr']

    def _getAnswer( self ):
        return fossilize(DBHelpers().getRoomsByUser(self._user))



class AddConference2Room( ServiceBase, Observable ):

    def __init__(self, params, remoteHost, session):
        ServiceBase.__init__(self, params, remoteHost, session)

    def _checkParams(self):
        self._rooms = self._params['rooms']
        self._conference = self._params['conference']

    def _getAnswer( self ):
        rooms=[]
        ContextManager.getdefault('mailHelper', MailHelper())
        try:
            for roomID in self._rooms:
                try:
                    room = DBHelpers.getChatroom(roomID)
                except Exception, e:
                    Logger.get('InstantMessaging (XMPP-Indico server)').warning("The user %s tried to re-use the chat room %s, but it was deleted before he clicked the Add button: %s" %(self._aw.getUser().getFullName(), roomID, e))
                    raise NoReportError(_('Some of the rooms were deleted from the other conference(s) they belonged to. Please refresh your browser'))
                room.setConference(ConferenceHolder().getById(self._conference))
                self._notify('addConference2Room', {'room': room, 'conf': self._conference})
                rooms.append(room.fossilizeMultiConference(ConferenceHolder().getById(self._conference)))
        except NoReportError, e:
            Logger.get('InstantMessaging (XMPP-Indico server)').error("Error adding chat rooms. User: %s. Chat room: %s. Traceback: %s" %(self._aw.getUser().getFullName(), roomID, e))
            raise ServiceError(message = _('There was an error trying to add the chat rooms. Please refresh your browser and try again'))

        ContextManager.get('mailHelper').sendMails()
        return rooms


methodMap = {
    "XMPP.createRoom": CreateChatroom,
    "XMPP.editRoom": EditChatroom,
    "XMPP.deleteRoom": DeleteChatroom,
    "XMPP.getRoomPreferences": GetRoomPreferences,
    "XMPP.getRoomsByUser": GetRoomsByUser,
    "XMPP.addConference2Room": AddConference2Room
}
