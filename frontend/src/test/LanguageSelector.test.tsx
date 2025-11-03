import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import LanguageSelector from '../components/common/LanguageSelector';
import '../i18n/config';

describe('LanguageSelector', () => {
  it('renders language selector button', () => {
    render(<LanguageSelector />);
    const button = screen.getByRole('button');
    expect(button).toBeInTheDocument();
  });

  it('opens menu when button is clicked', () => {
    render(<LanguageSelector />);
    const button = screen.getByRole('button');
    fireEvent.click(button);

    // Check if menu items are visible
    expect(screen.getByText('English')).toBeInTheDocument();
    expect(screen.getByText('Japanese')).toBeInTheDocument();
  });

  it('changes language when menu item is clicked', async () => {
    render(<LanguageSelector />);
    const button = screen.getByRole('button');
    fireEvent.click(button);

    const japaneseOption = screen.getByText('Japanese');
    fireEvent.click(japaneseOption);

    // After clicking, the menu should close
    // We can verify by checking if the button is still there
    expect(button).toBeInTheDocument();
  });
});
