export const monthToIndex = (monthKey) => {
  const [year, month] = String(monthKey || "")
    .split("-")
    .map(Number);
  if (!year || !month) return null;
  return year * 12 + (month - 1);
};

export const indexToMonth = (index) => {
  const year = Math.floor(index / 12);
  const month = (index % 12) + 1;
  return `${year}-${String(month).padStart(2, "0")}`;
};

export const addMonths = (monthKey, monthsToAdd) => {
  const base = monthToIndex(monthKey);
  if (base === null) return monthKey;
  return indexToMonth(base + monthsToAdd);
};

export const getMaxMonthToAllowed = (monthFrom, currentMonthKey) => {
  if (!monthFrom) return currentMonthKey;
  const cappedByRange = addMonths(monthFrom, 12);
  return cappedByRange < currentMonthKey ? cappedByRange : currentMonthKey;
};

export const clampMonthRange = (monthFrom, monthTo, currentMonthKey) => {
  if (!monthFrom || !monthTo) return monthTo;

  const startIdx = monthToIndex(monthFrom);
  const endIdx = monthToIndex(monthTo);
  if (startIdx === null || endIdx === null) return monthTo;

  if (endIdx < startIdx) {
    return monthFrom;
  }

  if (endIdx - startIdx > 12) {
    return addMonths(monthFrom, 12);
  }

  const currentIdx = monthToIndex(currentMonthKey);
  if (currentIdx !== null && endIdx > currentIdx) {
    return currentMonthKey;
  }

  return monthTo;
};

export const buildContinuousMonthlySeries = (monthlySeries, from, to) => {
  if (!from || !to || from > to) return [];

  const valueMap = new Map(
    monthlySeries.map((item) => [item.month, item.interviews]),
  );
  const result = [];

  const [fromYear, fromMonth] = from.split("-").map(Number);
  const [toYear, toMonth] = to.split("-").map(Number);

  let year = fromYear;
  let month = fromMonth;

  while (year < toYear || (year === toYear && month <= toMonth)) {
    const key = `${year}-${String(month).padStart(2, "0")}`;
    result.push({
      month: key,
      interviews: Number(valueMap.get(key) || 0),
    });

    month += 1;
    if (month > 12) {
      month = 1;
      year += 1;
    }
  }

  return result;
};
