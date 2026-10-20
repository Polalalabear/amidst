// V2-5 fills this in. V2-1 only reserves the mount point; app.mjs calls mount(ctx) with
// { store, slots, shell } where slots.timeline is the element this module owns. Do not add other imports to app.mjs.
export function mount(/* { store, slots, shell } */) {}
