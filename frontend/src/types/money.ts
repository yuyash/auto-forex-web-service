export interface MoneyAmount {
  amount: string;
  currency: string;
}

export interface MoneyAmountLike {
  amount?: string | number | null;
  currency?: string | null;
}
