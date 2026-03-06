/**
 * Unit tests for focus management utilities.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import {
  getFocusableElements,
  focusFirstElement,
  focusLastElement,
  isFocusable,
  saveFocus,
} from '../../../src/utils/focusManagement';

function createContainer(html: string): HTMLElement {
  const div = document.createElement('div');
  div.innerHTML = html;
  document.body.appendChild(div);
  return div;
}

describe('getFocusableElements', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
  });

  it('finds buttons, inputs, links, and textareas', () => {
    const container = createContainer(`
      <button>Click</button>
      <input type="text" />
      <a href="/test">Link</a>
      <textarea></textarea>
      <select><option>A</option></select>
    `);
    expect(getFocusableElements(container)).toHaveLength(5);
  });

  it('excludes disabled elements', () => {
    const container = createContainer(`
      <button disabled>Disabled</button>
      <button>Enabled</button>
      <input disabled />
    `);
    expect(getFocusableElements(container)).toHaveLength(1);
  });

  it('excludes tabindex="-1"', () => {
    const container = createContainer(`
      <button>Normal</button>
      <div tabindex="-1">Not focusable</div>
      <div tabindex="0">Focusable</div>
    `);
    expect(getFocusableElements(container)).toHaveLength(2);
  });
});

describe('focusFirstElement', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
  });

  it('focuses the first focusable element', () => {
    const container = createContainer(`
      <span>Text</span>
      <button id="first">First</button>
      <button id="second">Second</button>
    `);
    focusFirstElement(container);
    expect(document.activeElement?.id).toBe('first');
  });
});

describe('focusLastElement', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
  });

  it('focuses the last focusable element', () => {
    const container = createContainer(`
      <button id="first">First</button>
      <button id="last">Last</button>
    `);
    focusLastElement(container);
    expect(document.activeElement?.id).toBe('last');
  });
});

describe('isFocusable', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
  });

  it('returns true for buttons', () => {
    const btn = document.createElement('button');
    document.body.appendChild(btn);
    expect(isFocusable(btn)).toBe(true);
  });

  it('returns false for disabled buttons', () => {
    const btn = document.createElement('button');
    btn.disabled = true;
    document.body.appendChild(btn);
    expect(isFocusable(btn)).toBe(false);
  });

  it('returns false for plain divs', () => {
    const div = document.createElement('div');
    document.body.appendChild(div);
    expect(isFocusable(div)).toBe(false);
  });

  it('returns true for elements with tabindex="0"', () => {
    const div = document.createElement('div');
    div.setAttribute('tabindex', '0');
    document.body.appendChild(div);
    expect(isFocusable(div)).toBe(true);
  });
});

describe('saveFocus', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
  });

  it('restores focus to previously active element', () => {
    const container = createContainer(`
      <button id="original">Original</button>
      <button id="other">Other</button>
    `);
    const original = container.querySelector('#original') as HTMLElement;
    const other = container.querySelector('#other') as HTMLElement;

    original.focus();
    const restore = saveFocus();

    other.focus();
    expect(document.activeElement?.id).toBe('other');

    restore();
    expect(document.activeElement?.id).toBe('original');
  });
});
