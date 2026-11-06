import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "tech.rastescan.app",
  appName: "RasteScan",
  webDir: "dist",
  android: { allowMixedContent: false },
};

export default config;
