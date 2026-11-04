# Android app and Google Play internal testing

The Android app is the same React app wrapped with Capacitor (`web/android`). It talks to the CloudFront address.

## Build (on a computer with Android Studio)
```bash
cd web
npm ci
# put your CloudFront address in .env.android first
npm run build:android
npx cap open android
```
In Android Studio: **Build → Generate Signed App Bundle** → create a new upload keystore
(keep the .jks file and passwords outside the repo) → release → `app-release.aab`.

To test on a phone first: plug it in with USB debugging on, then **Run ▶** in Android Studio.

## Upload to Play internal testing
1. Play Console → Create app → name **RasteScan**, app, free.
2. Testing → **Internal testing** → Create new release → upload `app-release.aab`.
3. Testers tab → create a list → add Gmail addresses (team + any judges you know). Copy the **opt-in link**.
4. App content: privacy policy URL = `https://<your-cloudfront>/privacy.html`; answer data safety
   (collects photos and approximate/precise location, for app functionality; not shared).
5. Roll out. Testers open the opt-in link on their phone, accept, then install from Play.

Internal testing normally becomes available within minutes to a few hours. Upload the night before, not on the day.
Closed and open testing go through review and can take days, so don't use them for the expo.

## Version bumps
Each new upload needs a higher `versionCode` in `web/android/app/build.gradle`.
