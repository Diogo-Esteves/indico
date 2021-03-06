/* This file is part of Indico.
 * Copyright (C) 2002 - 2019 European Organization for Nuclear Research (CERN).
 *
 * Indico is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License as
 * published by the Free Software Foundation; either version 3 of the
 * License, or (at your option) any later version.
 *
 * Indico is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Indico; if not, see <http://www.gnu.org/licenses/>.
 */

import principalsURL from 'indico-url:core.principals';

import _ from 'lodash';
import React, {useEffect, useState} from 'react';
import PropTypes from 'prop-types';
import {Button, Icon, List, Loader} from 'semantic-ui-react';
import {Translate} from 'indico/react/i18n';
import {indicoAxios, handleAxiosError} from 'indico/utils/axios';
import {camelizeKeys} from 'indico/utils/case';
import {UserSearch, GroupSearch} from './Search';

import './PrincipalListField.module.scss';


/**
 * A field that lets the user select a list of users/groups
 */
const PrincipalListField = (props) => {
    const {value, disabled, onChange, onFocus, onBlur, withGroups, favoriteUsersController} = props;
    const [favoriteUsers, [handleAddFavorite, handleDelFavorite]] = favoriteUsersController;

    // keep track of details for each entry
    const [identifierMap, setIdentifierMap] = useState({});

    const isGroup = identifier => identifier.startsWith('Group:');
    const markTouched = () => {
        onFocus();
        onBlur();
    };
    const handleDelete = identifier => {
        onChange(value.filter(x => x !== identifier));
        markTouched();
    };
    const handleAddItems = data => {
        setIdentifierMap(prev => ({...prev, ..._.keyBy(data, 'identifier')}));
        onChange([...value, ...data.map(x => x.identifier)]);
        markTouched();
    };

    // fetch missing details
    useEffect(() => {
        const missingData = _.difference(value, Object.keys(identifierMap));
        if (!missingData.length) {
            return;
        }

        const source = indicoAxios.CancelToken.source();
        (async () => {
            let response;
            try {
                response = await indicoAxios.post(principalsURL(), {values: missingData}, {cancelToken: source.token});
            } catch (error) {
                handleAxiosError(error);
                return;
            }
            setIdentifierMap(prev => ({...prev, ...camelizeKeys(response.data)}));
        })();

        return () => {
            source.cancel();
        };
    }, [identifierMap, value]);

    const entries = _.sortBy(
        value.filter(x => x in identifierMap).map(x => identifierMap[x]),
        x => `${x.group ? 0 : 1}-${x.name.toLowerCase()}`
    );
    const pendingEntries = _.sortBy(
        value.filter(x => !(x in identifierMap)).map(x => ({identifier: x, group: isGroup(x)})),
        x => `${x.group ? 0 : 1}-${x.identifier.toLowerCase()}`
    );

    return (
        <>
            <List divided relaxed styleName="list">
                {entries.map(data => (
                    <PrincipalListItem key={data.identifier}
                                       name={data.name}
                                       detail={data.detail}
                                       isGroup={data.group}
                                       favorite={!data.group && data.userId in favoriteUsers}
                                       onDelete={() => !disabled && handleDelete(data.identifier)}
                                       onAddFavorite={() => !disabled && handleAddFavorite(data.userId)}
                                       onDelFavorite={() => !disabled && handleDelFavorite(data.userId)}
                                       disabled={disabled} />
                ))}
                {pendingEntries.map(data => (
                    <PendingPrincipalListItem key={data.identifier} isGroup={data.group} />
                ))}
                {!value.length && (
                    <List.Item styleName="empty">
                        <Translate>
                            This list is currently empty
                        </Translate>
                    </List.Item>
                )}
            </List>
            <Button.Group>
                <Button icon="add" as="div" disabled />
                <UserSearch existing={value} onAddItems={handleAddItems} favorites={favoriteUsers}
                            disabled={disabled} />
                {withGroups && <GroupSearch existing={value} onAddItems={handleAddItems} disabled={disabled} />}
            </Button.Group>
        </>
    );
};

PrincipalListField.propTypes = {
    value: PropTypes.arrayOf(PropTypes.string).isRequired,
    disabled: PropTypes.bool.isRequired,
    onChange: PropTypes.func.isRequired,
    onFocus: PropTypes.func.isRequired,
    onBlur: PropTypes.func.isRequired,
    favoriteUsersController: PropTypes.array.isRequired,
    withGroups: PropTypes.bool,
};

PrincipalListField.defaultProps = {
    withGroups: false,
};

// eslint-disable-next-line react/prop-types
const PendingPrincipalListItem = ({isGroup}) => (
    <List.Item>
        <div styleName="item">
            <div styleName="icon">
                <Icon name={isGroup ? 'users' : 'user'} size="large" />
            </div>
            <div styleName="content">
                <List.Content>
                    {isGroup
                        ? <Translate>Unknown group</Translate>
                        : <Translate>Unknown user</Translate>}
                </List.Content>
            </div>
            <div styleName="loader">
                <Loader active inline size="small" />
            </div>
        </div>
    </List.Item>
);

// eslint-disable-next-line react/prop-types
const PrincipalListItem = ({isGroup, name, detail, onDelete, onAddFavorite, onDelFavorite, disabled, favorite}) => (
    <List.Item>
        <div styleName="item">
            <div styleName="icon">
                <Icon name={isGroup ? 'users' : 'user'} size="large" />
            </div>
            <div styleName="content">
                <List.Content>
                    {name}
                </List.Content>
                {detail && (
                    <List.Description>
                        <small>{detail}</small>
                    </List.Description>
                )}
            </div>
            <div styleName="actions">
                {!isGroup && (
                    favorite ? (
                        <Icon styleName="button favorite active" name="star" size="large"
                              onClick={onDelFavorite} disabled={disabled} />
                    ) : (
                        <Icon styleName="button favorite" name="star outline" size="large"
                              onClick={onAddFavorite} disabled={disabled} />
                    )
                )}
                <Icon styleName="button delete" name="remove" size="large"
                      onClick={onDelete} disabled={disabled} />
            </div>
        </div>
    </List.Item>
);

export default React.memo(PrincipalListField);
