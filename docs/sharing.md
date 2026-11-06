# Let other devices use the app from your Mac

Your Mac runs the app; phones and laptops open it in their browser.

| Goal | Command | Address |
|---|---|---|
| Phones/laptops on the **same Wi-Fi**, with your normal dev setup | `make api` and `make web` (as usual), then `make lan` to print the address | `http://<your Mac's address>:5173` |
| Same Wi-Fi, **one port**, like production (builds the web app first) | `make share` | `http://<your Mac's address>:8000` |
| **Anyone, anywhere** (public https link) | `make share` in one terminal, `make tunnel` in another | the `https://….trycloudflare.com` link it prints |

## CORS
- Through `:5173` (Vite) or `:8000` (`make share`) the page and the API share one address, so **there is no CORS at all**.
- When a page on another origin calls the API directly (for example the Android app or a page on `http://192.168.x.x:5173` calling
  `http://192.168.x.x:8000`), `CORS_ALLOW_LAN=1` allows pages from private networks only (`localhost`, `10.x`, `192.168.x`,
  `172.16-31.x`, `*.local`). `make api` and `make share` turn it on. Public websites stay blocked.
- `CORS_ORIGINS=https://yoursite.example,...` lists exact origins for production, and `CORS_ORIGINS=*` allows any origin.

## Things to know
- **Camera and GPS need https** on phones. Over plain `http://192.168…` the browser blocks location, so use `make tunnel`
  (cloudflared, no account) or pick the spot on the map.
- macOS may ask to **allow incoming connections** for Python/node: click Allow. A Wi-Fi with "client isolation" (hotels,
  some campuses) stops devices from reaching each other; use `make tunnel` there.
- A tunnel link is public and anyone who has it can open the app and send reports. Close it with `Ctrl+C` when done.
- `make share` has **no officer PIN** (only officer accounts) unless you set `DASHBOARD_PIN`. Set `ADMIN_EMAIL` and a strong
  `ADMIN_PASSWORD` before opening the app to others.
