// Node-Ladehaken: 'three' und 'three/addons/…' auf die Ersatzmodule umleiten.
const here = new URL('./', import.meta.url);
export async function resolve(specifier, context, next) {
  if (specifier === 'three') return { url: new URL('three-stub.mjs', here).href, shortCircuit: true };
  if (specifier.startsWith('three/addons/')) return { url: new URL('addons/stubs.mjs', here).href, shortCircuit: true };
  return next(specifier, context);
}
