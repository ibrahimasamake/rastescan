# RasteScan mobile (Flutter)

Citizen app: report road damage with the camera, watch the AI analysis, browse all reports, live map with an auto tour, my reports, impact.
Android package `tech.rastescan.app`. Talks to `https://dev.samibrahima.tech` by default.

```bash
flutter pub get
flutter run                                   # on a connected phone/emulator
flutter run --dart-define=API_BASE=https://your-api.example.com
flutter test
flutter build appbundle --release             # signed bundle for Google Play
# build/app/outputs/bundle/release/app-release.aab
```

## Signing (never commit these)
`android/upload-keystore.jks` and `android/key.properties` are git-ignored. Keep a private backup.
Use **Play App Signing** (the default): Google keeps the real app key, this is only the *upload* key, and Play can reset it if it is lost.
Without `key.properties` the release build falls back to the debug key (fine for local tests, rejected by Play).

## Google Play internal testing
1. Play Console > Create app: name RasteScan, language, App, Free.
2. App content: privacy policy URL `https://dev.samibrahima.tech/privacy.html`, Data safety (photos, approximate/precise location, device id, all sent to the server, not sold; a report's coordinates are also sent to OpenStreetMap to look up its PIN code and address), content rating, target audience, ads = none.
3. Testing > Internal testing > Create new release > upload `app-release.aab` > release name `1.0.1 (2)` > Save > Review > Start rollout.
4. Testers tab: create an email list, add the testers' Google accounts, copy the opt-in link and send it to them.
5. Next uploads: bump `version:` in `pubspec.yaml` (for example `1.0.2+3`, the number after + must increase every time).

The server must stay reachable over https. Before real use, point `API_BASE` at a stable deployed server, not the Mac tunnel.
