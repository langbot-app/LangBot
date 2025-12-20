import { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { FilterState, TimeRangeOption, DateRange } from '../types/monitoring';
import { getPresetDateRange } from '../utils/dateUtils';

/**
 * Custom hook for managing monitoring filters
 */
export function useMonitoringFilters() {
  const searchParams = useSearchParams();

  // Initialize filters from URL params
  const [selectedBots, setSelectedBots] = useState<string[]>(() => {
    const botId = searchParams.get('botId');
    return botId ? [botId] : [];
  });

  const [selectedPipelines, setSelectedPipelines] = useState<string[]>(() => {
    const pipelineId = searchParams.get('pipelineId');
    return pipelineId ? [pipelineId] : [];
  });

  const [timeRange, setTimeRange] = useState<TimeRangeOption>('last24Hours');
  const [customDateRange, setCustomDateRange] = useState<DateRange | null>(null);

  // Get the active date range (either preset or custom)
  const getActiveDateRange = (): DateRange | null => {
    if (timeRange === 'custom' && customDateRange) {
      return customDateRange;
    }
    return getPresetDateRange(timeRange);
  };

  // Reset all filters
  const resetFilters = () => {
    setSelectedBots([]);
    setSelectedPipelines([]);
    setTimeRange('last24Hours');
    setCustomDateRange(null);
  };

  // Get the current filter state
  const filterState: FilterState = {
    selectedBots,
    selectedPipelines,
    timeRange,
    customDateRange,
  };

  return {
    selectedBots,
    setSelectedBots,
    selectedPipelines,
    setSelectedPipelines,
    timeRange,
    setTimeRange,
    customDateRange,
    setCustomDateRange,
    getActiveDateRange,
    resetFilters,
    filterState,
  };
}
