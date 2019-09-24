[![Build Status](https://travis-ci.org/mozilla-services/tokenserver.png?branch=master)](https://travis-ci.org/mozilla-services/tokenserver)
[![Docker Build Status](https://circleci.com/gh/mozilla-services/tokenserver/tree/master.svg?style=shield&circle-token=0fdb6d8d80e18f180132ea25cf9f75a38828591a)](https://circleci.com/gh/mozilla-services/tokenserver)

# Firefox Sync TokenServer

This service is responsible for allocating Firefox Sync users to one of several Sync Storage nodes.
It provides the "glue" between [Firefox Accounts](https://github.com/mozilla/fxa/) and the
[SyncStorage](https://github.com/mozilla-services/server-syncstorage) API, and handles:

* Checking the user's credentials as provided by FxA
* Sharding users across storage nodes in a way that evenly distributes server load
* Re-assigning the user to a new storage node if their FxA encryption key changes
* Cleaning up old data from e.g. deleted accounts

The service was originallly conceived to be a general-purpose mechanism for connecting users
to multiple different Mozilla-run services, and you can see some of the historical context
for that original design [here](https://wiki.mozilla.org/Services/Sagrada/TokenServer)
and [here](https://mozilla-services.readthedocs.io/en/latest/token/index.html).

In practice today, it is only used for connecting to Firefox Sync.

## How to run the server

Like this:

    $ bin/paster serve etc/tokenserver-dev.ini

## API

Firfox Sync clients must first obtain user credentials from FxA, which can be either:

* A BrowserID assertion with audience of `https://token.services.mozilla.com/`
* An OAuth access token bearing the scope `https://identity.mozilla.com/apps/oldsync`

They then provide this in the `Authorization` header of a `GET` request to the Tokenserver,
which will respond with the URL of the user's sync storage node, and some short-lived credentials
that can be used to access it.

More detailed API documentation is available [here](https://mozilla-services.readthedocs.io/en/latest/token/apis.html).

### Using BrowserID

To access the user's sync data using BrowserID, the client must obtain a BrowserID assertion
with audience matching the tokenserver's public URL, as well as the user's Sync encryption key.
They send the BrowserID assertion in the `Authorization` header, and the first half of the
hex-encoded SHA256 digest of the encryption key in the `X-Client-State` header, like so:
```
GET /1.0/sync/1.5
Host: token.services.mozilla.com
Authorization: BrowserID <assertion>
X-Client-State: <hex(sha256(kSync))[:32]>
```

### Using OAuth

To access the user's sync data using OAuth, the client must obtain an FxA OAuth access_token
with scope `https://identity.mozilla.com/apps/oldsync`, and the corresponding encryption key
as a JWK. They send the OAuth token in the `Authorization` header, and the `kid` field of the
encryption key in the `X-KeyID` header, like so:

```
GET /1.0/sync/1.5
Host: token.services.mozilla.com
Authorization: Bearer <access_token>
X-KeyID: <JWK['kid']>
```

### Response

The tokenserver will validate the provided credentials, and either look up the user's existing
storage node allocation or assign them to a new one.  It responds with the location of the
storage node and a set of short-lived credentials that can be used to access it:

```
{
 'id': <token>,
 'key': <request-signing secret>,
 'api_endpoint': 'https://db42.sync.services.mozilla.com/1.5/12345',
 'uid': 12345,
 'duration': 300,
}
```

### Storage Token

The value of `<token>` is intended to be opaque to the client, but is in fact an encoded JSON blob
signed using a secret key shared between the tokenserver and the storage nodes.  This allows
the tokenserver to securely communicate information about the user to their storage node.
The fields contained therein include:

* `uid`: A numeric userid that uniquely identifies this user, on this storage node, using this encryption key
* `node`: The intended storage node on which these credentials can be used
* `expires`: A timestamp for when the credentials expire
* `fxa_uid`: The user's stable FxA user id, as a hex string
* `fxa_kid`: The key-id of the JWK representing the user's sync encryption key


## Data Model

The core of the TokenServer's data model is a table named `users` that maps each user to their storage
node, and that provides enough information to update that mapping over time.  Each row in the table
contains the following fields:

* `uid`: Auto-incrementing numeric userid, created automtically for each row.
* `service`: The service the user is accessing; in practice this is always `sync-1.5`.
* `email`: Stable identifier for the user; in practice this is always `<fxa_uid>@api.accounts.firefox.com`.
* `nodeid`: The storage node to which the user has been assigned.
* `generation`: A monotonically increasing number provided by the FxA server, indicating
                the last time at which the user's login credentials were changed.
* `client_state`: The hash of the user's sync encryption key.
* `created_at`: Timestamp at which this node-assignment record was created.
* `replaced_at`: Timestamp at which this node-assignment record was replaced by a newer assignment, if any.

As you can see, this table contains some unnecessarily general names; these are a legacy of earlier plans
to re-use Tokenserver for multiple Mozilla services and with multiple identity providers.

The `generation` column is used to detect when the user's FxA credentials have been changed
and to lock out clients that have not been updated with the latest credentials.
Tokenserver tracks the highest value of `generation` that it has ever seen for a user,
and rejects BrowserID assertions in which the `generation` number is less than that high-water mark.

The `client_state` column is used to detect when the user's encryption key changes.
When it sees a new value for `client_state`, Tokenserver will replace the user's node assignment
with a new one, so that data encrypted with the new key will be written into a different
storage "bucket" on the storage nodes. Tokenserver communicates this value to the storage nodes
in the `fxa_kid` field (which unfortunately differs from the `X-KeyID` header used by OAuth clients,
due to some inconsistencies in tracking the timestamp at which the key material changed).

When replacing a user's node assignment, the previous column is not deleted immediately.
Instead, it is marked as "replaced" by setting the `replaced_at` timestamp, and then a background
job periodically purges replaced rows (including making a `DELETE` request to the storage node
to clean up any old data stored under that `uid`).

For this scheme to work as intended, it's expected that storage nodes will index user data by either:

1. The tuple `(fxa_uid, fxa_kid)`, which identifies a consistent set of sync data for a particular
   user, encrypted using a particular key.
2. The numeric `uid`, which changes whenever either of the above two values change.