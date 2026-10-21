export const WIZARD_STEPS = ['Job details', 'Hiring pipeline', 'Online assessment', 'Schedule & review'];

export function resizeSection(section, count) {
  const bounded = Math.max(0, Math.min(section.type === 'mcq' ? 100 : 10, count));
  return { ...section, count: bounded,
    difficulty: { easy: 0, medium: bounded, hard: 0 },
    marks: Array.from({ length: bounded }, (_, i) => section.marks[i] ?? (section.type === 'mcq' ? 1 : 25)),
    weight: bounded ? section.weight || 25 : 0,
    duration_minutes: bounded ? section.duration_minutes || 20 : 0,
  };
}

export function localInput(value, zone) {
  if (!value) return '';
  if (/^\d{4}-\d\d-\d\dT\d\d:\d\d$/.test(value)) return value;
  try {
    const parts = new Intl.DateTimeFormat('en-GB', { timeZone: zone, year: 'numeric', month: '2-digit',
      day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(new Date(value));
    const p = Object.fromEntries(parts.map(x => [x.type, x.value]));
    return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
  } catch { return ''; }
}

export function withExistingDeadline(configuration, deadline) {
  if (!deadline) return configuration;
  const close = /^\d{4}-\d\d-\d\d$/.test(deadline) ? `${deadline}T23:59` : localInput(deadline, configuration.schedule.timezone);
  if (!close) return configuration;
  const after = new Date(`${close}Z`);
  if (!Number.isFinite(after.getTime())) return configuration;
  after.setUTCDate(after.getUTCDate() + 3);
  const screenClose = after.toISOString().slice(0, 16);
  after.setUTCDate(after.getUTCDate() + 1);
  after.setUTCHours(9, 0, 0, 0);
  const oaOpen = after.toISOString().slice(0, 16);
  // Resolve the unambiguous 09:00 wall time to UTC before adding 24 hours;
  // a local calendar day can be 23 or 25 hours at a DST boundary.
  const wall = after.getTime();
  let opening = new Date(wall);
  for (let i = 0; i < 3; i++) {
    const rendered = localInput(opening.toISOString(), configuration.schedule.timezone);
    if (!rendered) return configuration;
    opening = new Date(opening.getTime() + wall - new Date(`${rendered}Z`).getTime());
  }
  const cutoff = localInput(new Date(opening.getTime() + 24 * 60 * 60 * 1000).toISOString(), configuration.schedule.timezone);
  return { ...configuration, schedule: { ...configuration.schedule, application_closes_at: close,
    screening_opens_at: close, screening_closes_at: screenClose, oa_opens_at: oaOpen,
    oa_start_closes_at: cutoff } };
}

export function applyRoleTemplate(configuration, preset) {
  return { ...configuration, oa: { ...configuration.oa, template_id: preset.id,
    sections: structuredClone(preset.sections), duration_minutes: preset.duration_minutes } };
}
