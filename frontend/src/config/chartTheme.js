export const CHART_PALETTE = ['#644CF0', '#F4DA4C', '#ED9A51', '#22C55E', '#8B7AF5', '#09061B']
export const CHART_TEXT_COLOR = '#A0A0A8'
export const CHART_SPLIT_COLOR = '#F1F2F6'
export const CHART_BG = 'transparent'
export const CHART_SUCCESS = '#22C55E'
export const CHART_WARNING = '#ED9A51'
export const CHART_INFO = '#8B7AF5'

export const CHART_DEFAULTS = {
  backgroundColor: CHART_BG,
  textStyle: {
    fontFamily: 'Inter, -apple-system, sans-serif',
    color: CHART_TEXT_COLOR,
    fontSize: 13,
  },
  grid: {
    left: 50,
    right: 20,
    top: 24,
    bottom: 40,
    containLabel: false,
  },
  tooltip: {
    backgroundColor: '#fff',
    borderColor: CHART_SPLIT_COLOR,
    borderWidth: 1,
    borderRadius: 12,
    padding: [12, 16],
    textStyle: { color: '#09061B', fontSize: 14 },
    extraCssText: 'box-shadow: 0 4px 16px rgba(9,6,27,0.08);',
  },
  legend: {
    textStyle: { color: CHART_TEXT_COLOR, fontSize: 13, fontWeight: 500 },
    itemWidth: 8,
    itemHeight: 8,
    icon: 'circle',
    itemGap: 18,
  },
  xAxis: {
    axisLine: { lineStyle: { color: CHART_SPLIT_COLOR } },
    axisTick: { show: false },
    axisLabel: { color: CHART_TEXT_COLOR, fontSize: 13 },
  },
  yAxis: {
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: CHART_TEXT_COLOR, fontSize: 13 },
    splitLine: { lineStyle: { color: CHART_SPLIT_COLOR, type: 'dashed' } },
  },
}
