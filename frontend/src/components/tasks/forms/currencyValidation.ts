import { z } from 'zod';

export const currencyCodeSchema = z.preprocess(
  (value) =>
    String(value ?? '')
      .trim()
      .toUpperCase(),
  z.string().regex(/^[A-Z]{3}$/, 'Currency must be a 3-letter code')
);

export const optionalCurrencyCodeSchema = z.preprocess(
  (value) =>
    String(value ?? '')
      .trim()
      .toUpperCase(),
  z
    .union([z.literal(''), z.string().regex(/^[A-Z]{3}$/)])
    .optional()
    .default('')
);
