# Firebase Setup

Chass! uses Firebase Admin on the FastAPI server. The React frontend never receives
Firebase credentials and never accesses Firestore directly.

## 1. Create Firestore

1. Open the [Firebase Console](https://console.firebase.google.com/) and create a project.
2. Google Analytics is optional and is not required by Chass!.
3. Open **Build > Firestore Database** and select **Create database**.
4. Choose the free **Standard edition**, the default database, and a region near the
   Render service.
5. Choose **Production mode** so browser access starts denied.
6. Copy the project ID from **Project settings > General**.

Do not enable billing. Chass! only needs the Spark plan's free Firestore database.

## 2. Create Server Credentials

1. Open **Project settings > Service accounts**.
2. Select **Firebase Admin SDK**.
3. Select **Generate new private key** and confirm.
4. Keep the downloaded JSON file private and outside this repository.

Encode the JSON as one line on macOS or Linux:

```bash
base64 < ~/Downloads/your-service-account.json | tr -d '\n'
```

On macOS, copy it directly and verify the clipboard without displaying the credential:

```bash
base64 < ~/Downloads/your-service-account.json | tr -d '\n' | pbcopy
pbpaste | python3 -c 'import base64,json,sys; value=json.loads(base64.b64decode(sys.stdin.read())); assert value.get("type") == "service_account"; print("Credential encoding is valid")'
```

The output is the value for `FIREBASE_CREDENTIALS_BASE64`. Never commit the JSON file or
the encoded value. Base64 is transport encoding, not encryption.

## 3. Configure Render Without Downtime

The new variables use `sync: false`, so an existing Render Blueprint does not add their
values automatically.

1. Open **Render > chass-api > Environment**.
2. Add `FIREBASE_PROJECT_ID` using the Firebase project ID.
3. Add `FIREBASE_CREDENTIALS_BASE64` using the encoded service-account JSON.
4. Keep the existing `TOKEN_SECRET` unchanged so existing seat tokens remain valid.
5. Initially keep `PERSISTENCE_BACKEND=sql` and deploy the new application code.
6. After the deployment succeeds, change `PERSISTENCE_BACKEND=firestore`.
7. Select **Save and deploy**.

The backend treats `project_id` inside the service-account JSON as authoritative. If
`FIREBASE_PROJECT_ID` differs, Render logs a warning and Chass! connects to the credential's
project rather than silently querying an inaccessible project.

Keep `DATABASE_URL` temporarily for rollback or data migration. It is ignored while
`PERSISTENCE_BACKEND=firestore` and can be removed after the cutover is verified.

## 4. Keep Firestore Private

The repository includes `firestore.rules`, which denies all browser reads and writes.
Firebase Admin bypasses these rules using server IAM credentials.

From the repository root, deploy the included rules and index configuration once:

```bash
npx firebase-tools login
npx firebase-tools deploy --only firestore --project your-firebase-project-id
```

This also prevents Firestore from indexing the serialized board-state field, which does
not need to be searched. Run the same command again after pulling any update that changes
`firestore.indexes.json`; the move-history index is required before paginated histories
can be loaded in production.

In **Firestore Database > Rules**, confirm the deployed rule is equivalent to:

```text
match /{document=**} {
  allow read, write: if false;
}
```

Do not add public rules. A future account feature can introduce Firebase Authentication
and user-specific policies separately.

## 5. Optional: Preserve Existing Games

Existing Supabase documents do not move automatically. If old test games are disposable,
skip this section and start with an empty Firestore database.

To preserve them, first resume Supabase and set these variables locally:

```bash
export DATABASE_URL='your-supabase-session-pooler-url'
export FIREBASE_PROJECT_ID='your-firebase-project-id'
export FIREBASE_CREDENTIALS_BASE64='your-encoded-service-account-json'
```

Preview the migration:

```bash
source .venv/bin/activate
python -m scripts.migrate_sql_to_firestore
```

Apply it:

```bash
python -m scripts.migrate_sql_to_firestore --apply
```

The migration preserves game IDs, versions, token hashes, invites, and move audits. It
skips expired or inactive games by default so abandoned records are not moved. Keep
Render's existing `TOKEN_SECRET`; changing it invalidates previously issued seat tokens.

## 6. Inactive-Game Retention

The Render configuration defaults to:

```text
INVITE_TTL_HOURS=24
GAME_IDLE_TTL_HOURS=24
GAME_CLEANUP_INTERVAL_MINUTES=15
```

Creation, joining, replacing an invitation, moves, resets, and customization renew the
game's idle deadline. Reads, WebSocket reconnects, presence, and pings do not. After 24
hours without a game change, Chass! removes its game document, player seats, invitation
records, and move audits.

Cleanup runs when FastAPI starts and every 15 minutes while it is awake. If free Render
hosting is asleep at the deadline, deletion runs when the backend next wakes. Direct
access to an expired game also triggers its cleanup. This application-managed process
avoids requiring Firestore's billed TTL deletion feature.

## 7. Verify the Cutover

1. Open the Render health endpoint and confirm `"persistence":"firestore"`.
2. Create and move in a local game on the deployed frontend.
3. Create an online room and copy its invitation.
4. Join from an incognito window or second device.
5. Make a move from each side and refresh both browsers.
6. Confirm `games`, `game_players`, `game_invites`, and `moves` appear in Firestore's Data
   tab.

If startup fails, set `PERSISTENCE_BACKEND=sql` in Render and redeploy. This immediately
returns the backend to the existing database while the Firebase configuration is fixed.

If `/health` works but creating or loading a game reports that storage is unavailable,
check the Render log generated by that game request. Chass! returns HTTP `503`, preserves
CORS headers, logs the Firebase exception, and refreshes its cached Firestore client for
the next attempt. Confirm that the Firestore database still exists, the service-account
key is active, and the project has not reached a free-tier quota before retrying.
