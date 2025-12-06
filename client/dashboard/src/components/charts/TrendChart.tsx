import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
  BarChart,
  Bar,
  Legend,
} from 'recharts';

export type ChartType = 'line' | 'area' | 'bar';

interface DataPoint {
  date: string;
  [key: string]: string | number;
}

interface SeriesConfig {
  key: string;
  name: string;
  color: string;
}

interface TrendChartProps {
  data: DataPoint[];
  series: SeriesConfig[];
  type?: ChartType;
  height?: number;
  showGrid?: boolean;
  showLegend?: boolean;
  yAxisDomain?: [number | 'auto', number | 'auto'];
}

// Custom tooltip component
function CustomTooltip({ active, payload, label }: any) {
  if (active && payload && payload.length) {
    return (
      <div className="bg-bg-secondary border border-bg-hover rounded-lg p-3 shadow-lg">
        <p className="text-xs text-text-muted mb-2">{label}</p>
        {payload.map((entry: any, index: number) => (
          <div key={index} className="flex items-center gap-2 text-sm">
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: entry.color }}
            />
            <span className="text-text-secondary">{entry.name}:</span>
            <span className="text-text-primary font-medium">{entry.value}</span>
          </div>
        ))}
      </div>
    );
  }
  return null;
}

export function TrendChart({
  data,
  series,
  type = 'line',
  height = 200,
  showGrid = true,
  showLegend = false,
  yAxisDomain,
}: TrendChartProps) {
  // Format date for display
  const formattedData = data.map((d) => ({
    ...d,
    displayDate: new Date(d.date).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    }),
  }));

  const commonProps = {
    data: formattedData,
    margin: { top: 10, right: 10, left: -20, bottom: 0 },
  };

  const axisProps = {
    xAxis: (
      <XAxis
        dataKey="displayDate"
        tick={{ fill: '#94a3b8', fontSize: 11 }}
        tickLine={false}
        axisLine={{ stroke: '#334155' }}
      />
    ),
    yAxis: (
      <YAxis
        tick={{ fill: '#94a3b8', fontSize: 11 }}
        tickLine={false}
        axisLine={false}
        domain={yAxisDomain}
      />
    ),
    grid: showGrid ? (
      <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
    ) : null,
  };

  const renderChart = () => {
    switch (type) {
      case 'area':
        return (
          <AreaChart {...commonProps}>
            {axisProps.grid}
            {axisProps.xAxis}
            {axisProps.yAxis}
            <Tooltip content={<CustomTooltip />} />
            {showLegend && <Legend />}
            {series.map((s) => (
              <Area
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.name}
                stroke={s.color}
                fill={s.color}
                fillOpacity={0.2}
                strokeWidth={2}
              />
            ))}
          </AreaChart>
        );
      case 'bar':
        return (
          <BarChart {...commonProps}>
            {axisProps.grid}
            {axisProps.xAxis}
            {axisProps.yAxis}
            <Tooltip content={<CustomTooltip />} />
            {showLegend && <Legend />}
            {series.map((s) => (
              <Bar
                key={s.key}
                dataKey={s.key}
                name={s.name}
                fill={s.color}
                radius={[4, 4, 0, 0]}
              />
            ))}
          </BarChart>
        );
      default:
        return (
          <LineChart {...commonProps}>
            {axisProps.grid}
            {axisProps.xAxis}
            {axisProps.yAxis}
            <Tooltip content={<CustomTooltip />} />
            {showLegend && <Legend />}
            {series.map((s) => (
              <Line
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.name}
                stroke={s.color}
                strokeWidth={2}
                dot={{ fill: s.color, strokeWidth: 0, r: 3 }}
                activeDot={{ r: 5, strokeWidth: 0 }}
              />
            ))}
          </LineChart>
        );
    }
  };

  return (
    <ResponsiveContainer width="100%" height={height}>
      {renderChart()}
    </ResponsiveContainer>
  );
}
