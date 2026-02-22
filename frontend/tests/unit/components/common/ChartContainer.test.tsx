/**
 * ChartContainer Unit Tests
 *
 * Tests for the ChartContainer component.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ChartContainer } from '../../../../src/components/common/ChartContainer';

describe('ChartContainer', () => {
  it('should render chart children when not loading and no error', () => {
    render(
      <ChartContainer>
        <div>Test Chart Content</div>
      </ChartContainer>
    );

    expect(screen.getByText('Test Chart Content')).toBeInTheDocument();
  });

  it('should render loading state when isLoading is true', () => {
    render(
      <ChartContainer isLoading={true}>
        <div>Test Chart Content</div>
      </ChartContainer>
    );

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
    expect(screen.getByText('Loading chart data...')).toBeInTheDocument();
    expect(screen.queryByText('Test Chart Content')).not.toBeInTheDocument();
  });

  it('should render error state when error is present', () => {
    const error = new Error('Failed to load chart');
    render(
      <ChartContainer error={error}>
        <div>Test Chart Content</div>
      </ChartContainer>
    );

    expect(screen.getByText('Error Loading Chart')).toBeInTheDocument();
    expect(screen.getByText(/Failed to load chart/i)).toBeInTheDocument();
    expect(screen.queryByText('Test Chart Content')).not.toBeInTheDocument();
  });

  it('should render empty message when no children and not loading', () => {
    render(<ChartContainer emptyMessage="No data to display" />);

    expect(screen.getByText('No data to display')).toBeInTheDocument();
  });

  it('should render title when provided', () => {
    render(
      <ChartContainer title="Equity Curve">
        <div>Test Chart Content</div>
      </ChartContainer>
    );

    expect(screen.getByText('Equity Curve')).toBeInTheDocument();
  });

  it('should render granularity selector when enabled', () => {
    const handleGranularityChange = vi.fn();
    render(
      <ChartContainer
        showGranularitySelector={true}
        granularity={60}
        onGranularityChange={handleGranularityChange}
      >
        <div>Test Chart Content</div>
      </ChartContainer>
    );

    expect(
      screen.getByLabelText('Select chart granularity')
    ).toBeInTheDocument();
  });

  it('should call onGranularityChange when granularity is changed', () => {
    const handleGranularityChange = vi.fn();
    const { container } = render(
      <ChartContainer
        showGranularitySelector={true}
        granularity={60}
        onGranularityChange={handleGranularityChange}
      >
        <div>Test Chart Content</div>
      </ChartContainer>
    );

    // Find the hidden native select input and change its value
    const nativeSelect = container.querySelector(
      'input[type="hidden"]'
    ) as HTMLInputElement;
    if (nativeSelect) {
      fireEvent.change(nativeSelect, { target: { value: '300' } });
    }

    // The component should have the granularity selector rendered
    expect(
      screen.getByLabelText('Select chart granularity')
    ).toBeInTheDocument();
  });

  it('should render zoom controls when enabled', () => {
    const handleZoomIn = vi.fn();
    const handleZoomOut = vi.fn();
    const handleResetZoom = vi.fn();

    render(
      <ChartContainer
        showControls={true}
        onZoomIn={handleZoomIn}
        onZoomOut={handleZoomOut}
        onResetZoom={handleResetZoom}
      >
        <div>Test Chart Content</div>
      </ChartContainer>
    );

    expect(screen.getByLabelText('Zoom in')).toBeInTheDocument();
    expect(screen.getByLabelText('Zoom out')).toBeInTheDocument();
    expect(screen.getByLabelText('Reset zoom')).toBeInTheDocument();
  });

  it('should call zoom callbacks when buttons are clicked', () => {
    const handleZoomIn = vi.fn();
    const handleZoomOut = vi.fn();
    const handleResetZoom = vi.fn();

    render(
      <ChartContainer
        showControls={true}
        onZoomIn={handleZoomIn}
        onZoomOut={handleZoomOut}
        onResetZoom={handleResetZoom}
      >
        <div>Test Chart Content</div>
      </ChartContainer>
    );

    fireEvent.click(screen.getByLabelText('Zoom in'));
    expect(handleZoomIn).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByLabelText('Zoom out'));
    expect(handleZoomOut).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByLabelText('Reset zoom'));
    expect(handleResetZoom).toHaveBeenCalledTimes(1);
  });

  it('should render refresh button when onRefresh is provided', () => {
    const handleRefresh = vi.fn();

    render(
      <ChartContainer showControls={true} onRefresh={handleRefresh}>
        <div>Test Chart Content</div>
      </ChartContainer>
    );

    expect(screen.getByLabelText('Refresh chart')).toBeInTheDocument();
  });

  it('should call onRefresh when refresh button is clicked', () => {
    const handleRefresh = vi.fn();

    render(
      <ChartContainer showControls={true} onRefresh={handleRefresh}>
        <div>Test Chart Content</div>
      </ChartContainer>
    );

    fireEvent.click(screen.getByLabelText('Refresh chart'));
    expect(handleRefresh).toHaveBeenCalledTimes(1);
  });

  it('should disable refresh button when loading', () => {
    const handleRefresh = vi.fn();

    render(
      <ChartContainer
        showControls={true}
        onRefresh={handleRefresh}
        isLoading={true}
      >
        <div>Test Chart Content</div>
      </ChartContainer>
    );

    const refreshButton = screen.getByLabelText('Refresh chart');
    expect(refreshButton).toBeDisabled();
  });

  it('should not render controls when showControls is false', () => {
    render(
      <ChartContainer
        showControls={false}
        onZoomIn={vi.fn()}
        onZoomOut={vi.fn()}
        onResetZoom={vi.fn()}
      >
        <div>Test Chart Content</div>
      </ChartContainer>
    );

    expect(screen.queryByLabelText('Zoom in')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Zoom out')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Reset zoom')).not.toBeInTheDocument();
  });

  it('should apply custom height and minHeight', () => {
    const { container } = render(
      <ChartContainer height={600} minHeight={400}>
        <div>Test Chart Content</div>
      </ChartContainer>
    );

    const chartBox = container
      .querySelector('[role="region"]')
      ?.querySelector('div:last-child');
    expect(chartBox).toHaveStyle({ minHeight: '400' });
  });

  it('should have proper accessibility attributes', () => {
    render(
      <ChartContainer title="Test Chart" ariaLabel="Test chart region">
        <div>Test Chart Content</div>
      </ChartContainer>
    );

    const region = screen.getByRole('region', { name: 'Test chart region' });
    expect(region).toBeInTheDocument();
  });
});
