/** True when animations should be gentle (fades only): the visitor asked for reduced motion and the link does not say ?motion=on. */
export function calmMotion(): boolean {
  const asked = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
  return asked && !/[?&]motion=on/.test(window.location.href);
}
