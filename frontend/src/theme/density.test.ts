import { describe, expect, it } from 'vitest';
import { spacingTokens, typographyTokens } from './density';

describe('density tokens', () => {
  it('uses canonical spacing steps', () => {
    expect(spacingTokens).toEqual({
      xxs: 0.5,
      xs: 1,
      sm: 1.5,
      md: 2,
      lg: 3,
    });
  });

  it('exposes shared typography variants for compact task surfaces', () => {
    expect(typographyTokens.sectionTitle).toBe('h6');
    expect(typographyTokens.subsectionTitle).toBe('subtitle1');
    expect(typographyTokens.body).toBe('body2');
    expect(typographyTokens.caption).toBe('caption');
  });
});
