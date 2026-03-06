/**
 * Integration tests for useTableRowSelection hook.
 * Verifies selection, deselection, select-all, and copy behavior.
 */

import { describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useTableRowSelection } from '../../../src/hooks/useTableRowSelection';

describe('useTableRowSelection', () => {
  it('starts with empty selection', () => {
    const { result } = renderHook(() => useTableRowSelection());
    expect(result.current.selectedRowIds.size).toBe(0);
  });

  it('toggles row selection on and off', () => {
    const { result } = renderHook(() => useTableRowSelection());

    act(() => result.current.toggleRowSelection('1'));
    expect(result.current.selectedRowIds.has('1')).toBe(true);

    act(() => result.current.toggleRowSelection('1'));
    expect(result.current.selectedRowIds.has('1')).toBe(false);
  });

  it('selects all rows on page', () => {
    const { result } = renderHook(() => useTableRowSelection());

    act(() => result.current.selectAllOnPage(['1', '2', '3']));
    expect(result.current.selectedRowIds.size).toBe(3);
  });

  it('deselects all rows on page', () => {
    const { result } = renderHook(() => useTableRowSelection());

    act(() => result.current.selectAllOnPage(['1', '2', '3']));
    act(() => result.current.deselectAllOnPage(['1', '2']));
    expect(result.current.selectedRowIds.size).toBe(1);
    expect(result.current.selectedRowIds.has('3')).toBe(true);
  });

  it('resets selection', () => {
    const { result } = renderHook(() => useTableRowSelection());

    act(() => result.current.selectAllOnPage(['1', '2']));
    act(() => result.current.resetSelection());
    expect(result.current.selectedRowIds.size).toBe(0);
  });

  it('isAllPageSelected returns true when all page rows selected', () => {
    const { result } = renderHook(() => useTableRowSelection());

    act(() => result.current.selectAllOnPage(['1', '2']));
    expect(result.current.isAllPageSelected(['1', '2'])).toBe(true);
    expect(result.current.isAllPageSelected(['1', '2', '3'])).toBe(false);
  });

  it('isAllPageSelected returns false for empty page', () => {
    const { result } = renderHook(() => useTableRowSelection());
    expect(result.current.isAllPageSelected([])).toBe(false);
  });

  it('isIndeterminate returns true for partial selection', () => {
    const { result } = renderHook(() => useTableRowSelection());

    act(() => result.current.toggleRowSelection('1'));
    expect(result.current.isIndeterminate(['1', '2'])).toBe(true);
    expect(result.current.isIndeterminate(['1'])).toBe(false); // all selected
  });

  it('copySelectedRows writes to clipboard', () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });

    const { result } = renderHook(() => useTableRowSelection());

    act(() => result.current.selectAllOnPage(['1', '2']));
    act(() => {
      result.current.copySelectedRows(
        ['ID', 'Name'],
        (id) => `${id}\tRow ${id}`
      );
    });

    expect(writeText).toHaveBeenCalledWith('ID\tName\n1\tRow 1\n2\tRow 2');
  });
});
