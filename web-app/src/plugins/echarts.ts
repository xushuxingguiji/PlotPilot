import type { App } from 'vue'
import ECharts from 'vue-echarts'
import {
  BarChart,
  LineChart,
  PieChart,
  ScatterChart,
  EffectScatterChart,
  RadarChart,
  HeatmapChart,
  GaugeChart,
  GraphChart,
  TreeChart,
  TreemapChart,
  SunburstChart,
  SankeyChart,
  FunnelChart,
  ParallelChart,
  CandlestickChart,
  BoxplotChart,
  ThemeRiverChart
} from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  PolarComponent,
  RadarComponent,
  GeoComponent,
  SingleAxisComponent,
  ParallelComponent,
  GraphicComponent,
  ToolboxComponent,
  DataZoomComponent,
  VisualMapComponent,
  LegendComponent,
  LegendScrollComponent,
  LegendPlainComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import * as echarts from 'echarts'

// Register components
ECharts.registerComponent(
  TitleComponent,
  TooltipComponent,
  GridComponent,
  PolarComponent,
  RadarComponent,
  GeoComponent,
  SingleAxisComponent,
  ParallelComponent,
  GraphicComponent,
  ToolboxComponent,
  DataZoomComponent,
  VisualMapComponent,
  LegendComponent,
  LegendScrollComponent,
  LegendPlainComponent
)

// Register charts
ECharts.registerChart(
  BarChart,
  LineChart,
  PieChart,
  ScatterChart,
  EffectScatterChart,
  RadarChart,
  HeatmapChart,
  GaugeChart,
  GraphChart,
  TreeChart,
  TreemapChart,
  SunburstChart,
  SankeyChart,
  FunnelChart,
  ParallelChart,
  CandlestickChart,
  BoxplotChart,
  ThemeRiverChart
)

// Register renderer
ECharts.registerRenderer(CanvasRenderer)

export default function installECharts(app: App) {
  app.component('VChart', ECharts)
  app.config.globalProperties.$echarts = echarts
}

export { echarts }
