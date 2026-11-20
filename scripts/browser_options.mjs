// Browser automation stays invisible unless the caller explicitly opts in.
export function headlessMode({argv = process.argv.slice(2), env = process.env} = {}) {
  return !(argv.includes('--headful') || env.AMIDST_HEADFUL === '1');
}
