# Migration Changes Summary

## Decision: Remove Vertical and Horizontal Lines

After attempting to implement vertical and horizontal lines in react-financial-charts, we've decided to remove these features from the migration scope due to technical limitations with the library.

### What Was Removed

1. **Vertical Lines** - Previously used to mark:
   - Backtest start/end times
   - Trading task start/stop times

2. **Horizontal Lines** - Previously used to mark:
   - Strategy floor levels
   - Support/resistance levels

### What Was Added Instead

**Start/End Markers** - Visual markers that serve the same purpose as vertical lines:

- **Start Marker**: Blue square positioned above the candle at the start timestamp
- **End Marker**: Purple triangle positioned above the candle at the end timestamp

These markers:

- Clearly indicate strategy/backtest boundaries
- Maintain position during pan/zoom operations
- Work reliably with the react-financial-charts annotation system
- Are easier to implement and maintain

### Files Updated

1. **POC Implementation**:
   - `frontend/src/components/chart/FinancialChartPOC.tsx` - Removed line code, added start/end markers

2. **Specification Documents**:
   - `.kiro/specs/react-financial-charts-migration/requirements.md` - Updated requirements to use markers instead of lines
   - `.kiro/specs/react-financial-charts-migration/design.md` - Needs update
   - `.kiro/specs/react-financial-charts-migration/tasks.md` - Needs update

### Next Steps

The design.md and tasks.md files still contain references to vertical and horizontal lines. These should be updated to reflect the new marker-based approach before implementation begins.

### Technical Rationale

The react-financial-charts library's annotation system is optimized for point-based markers rather than full-height/width lines. Attempts to create lines using:

- SVG path annotations with large heights
- Multiple stacked annotations
- TrendLine component (doesn't exist in this library)

All resulted in either NaN positioning errors or lines not rendering at all. The marker-based approach is more reliable and better supported by the library.
