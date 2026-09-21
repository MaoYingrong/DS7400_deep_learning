// Categorical colors for the 7 largest disciplines (validated with the dataviz palette checker).
// Everything else is folded into a neutral "Other" so colors stay distinguishable.
export const DISCIPLINE_COLORS = [
  '#2a78d6', // blue
  '#eb6834', // orange
  '#1baf7a', // aqua
  '#eda100', // yellow
  '#e87ba4', // magenta
  '#008300', // green
  '#4a3aa7', // violet
]
export const OTHER_COLOR = '#8a8985'
export const CITES_COLOR = '#0b0b0b' // edges from the selected paper to the papers it cites
export const CITED_BY_COLOR = '#e34948' // edges from citing papers into the selected paper

export function hexToRgb(hex) {
  const n = parseInt(hex.slice(1), 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

/** Map every discipline name to a hex color; the rest share OTHER_COLOR. */
export function buildColorMap(disciplines) {
  const map = {}
  disciplines.forEach((d, i) => {
    map[d] = i < DISCIPLINE_COLORS.length ? DISCIPLINE_COLORS[i] : OTHER_COLOR
  })
  return map
}
