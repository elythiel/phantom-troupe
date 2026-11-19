/**
 * The Phantom Troupe mod.
 *
 * It reads the archive and shows it. It drives nothing: the /troupe command
 * writes the state, and this file is only ever a reader. That is why nothing
 * here knows what a step means, only how to draw one, and why the plugin keeps
 * working with mods turned off.
 *
 * Two things are drawn: a row above the prompt naming the subject in progress,
 * and a /troupe-board command that prints the whole archive for the user's
 * eyes only.
 */

const REFRESH_MS = 10_000
const STEP_ORDER = ['ticket', 'refine', 'design', 'dev', 'review', 'test', 'ship']

// Read once at session start, refreshed on a timer and at the end of every turn.
let archiveRoot = null
let strings = null
let fallback = null
let current = null
let index = null
let fingerprint = ''

// --------------------------------------------------------------------- paths

function pluginRoot() {
  try {
    // .../phantom-troupe/hooks/register.js -> .../phantom-troupe
    const here = new URL('.', import.meta.url).pathname
    return here.replace(/\/hooks\/?$/, '')
  } catch {
    return null
  }
}

function expand($, value) {
  if (typeof value !== 'string') return value
  if (!value.startsWith('~')) return value
  const home = $.env.get('HOME') || $.env.get('USERPROFILE') || ''
  return home + value.slice(1)
}

async function readJson($, path) {
  if (!path) return null
  try {
    if (!(await $.fs.exists(path))) return null
    return JSON.parse(await $.fs.read(path))
  } catch {
    // A malformed file is the same as a missing one here: the mod shows less,
    // it never breaks the session over it.
    return null
  }
}

// -------------------------------------------------------------- configuration

async function findConfig($) {
  const fromEnv = $.env.get('TROUPE_CONFIG')
  const candidates = [
    fromEnv,
    '.troupe/config.json',
    expand($, '~/.config/phantom-troupe/config.json'),
  ].filter(Boolean)
  for (const candidate of candidates) {
    const found = await readJson($, candidate)
    if (found) return found
  }
  return null
}

async function loadStrings($, language) {
  const root = pluginRoot() || $.env.get('CLAUDE_PLUGIN_ROOT')
  if (!root) return
  fallback = await readJson($, `${root}/locales/en.json`)
  const tag = (language || 'en').trim()
  if (tag && tag !== 'en') {
    strings =
      (await readJson($, `${root}/locales/${tag}.json`)) ||
      (await readJson($, `${root}/locales/${tag.split('-')[0]}.json`))
  }
}

/** A string by dotted key, falling back to English key by key. */
function t(key, vars) {
  const walk = (source) => key.split('.').reduce((acc, part) => (acc == null ? acc : acc[part]), source)
  let value = walk(strings)
  if (typeof value !== 'string') value = walk(fallback)
  if (typeof value !== 'string') return key
  return value.replace(/\{(\w+)\}/g, (whole, name) =>
    vars && name in vars ? String(vars[name]) : whole,
  )
}

// ------------------------------------------------------------------- refresh

async function refresh($) {
  if (!archiveRoot) return false
  current = await readJson($, `${archiveRoot}/current.json`)
  index = await readJson($, `${archiveRoot}/index.json`)
  const next = JSON.stringify(current) + '|' + (index ? index.generatedAt : '')
  const changed = next !== fingerprint
  fingerprint = next
  return changed
}

function activeSubject() {
  return current && current.subjectId ? current : null
}

// ---------------------------------------------------------------------- band

function bandRow($, e) {
  const { Box, Text } = $.ui.resolve(e)
  const subject = activeSubject()
  if (!subject) return null

  const stepLabel = t(`steps.${subject.step}`)
  const pieces = [
    Text({ children: ['🕷 '] }),
    Text({ bold: true, children: [subject.subjectId] }),
  ]
  if (subject.title) {
    pieces.push(Text({ children: [`  ${subject.title}`] }))
  }
  pieces.push(
    Text({
      dimColor: true,
      children: [
        `  · ${t('band.stepOf', { current: subject.stepIndex, total: subject.stepTotal })} ${stepLabel}`,
      ],
    }),
  )
  if (subject.member) {
    pieces.push(Text({ dimColor: true, children: [` — ${subject.member}`] }))
  }
  if (subject.epic) {
    pieces.push(Text({ dimColor: true, children: [`  · ${t('band.epic', { name: subject.epic })}`] }))
  }
  return Box({ flexDirection: 'row', children: pieces })
}

// --------------------------------------------------------------------- board

function pad(value, width) {
  const text = value == null ? '' : String(value)
  return text.length >= width ? text : text + ' '.repeat(width - text.length)
}

function boardText() {
  if (!index || !Array.isArray(index.subjects) || index.subjects.length === 0) {
    return `${t('board.title')}\n\n${t('board.empty')}`
  }
  const rows = index.subjects
    .slice()
    .sort((a, b) => String(b.updatedAt || '').localeCompare(String(a.updatedAt || '')))

  const columns = [
    { key: 'id', head: t('board.column.subject'), get: (r) => r.id },
    { key: 'status', head: t('board.column.status'), get: (r) => t(`status.${r.status}`) },
    {
      key: 'step',
      head: t('board.column.step'),
      get: (r) => (r.step ? `${t(`steps.${r.step}`)} ${r.stepIndex}/${r.stepTotal}` : '—'),
    },
    { key: 'epic', head: t('board.column.epic'), get: (r) => r.epic || '' },
    { key: 'title', head: t('board.column.title'), get: (r) => r.title || '' },
  ]
  const widths = columns.map((column) =>
    Math.max(column.head.length, ...rows.map((row) => String(column.get(row) || '').length)),
  )

  const lines = [t('board.title'), '']
  lines.push(columns.map((column, i) => pad(column.head, widths[i])).join('  ').trimEnd())
  lines.push(widths.map((width) => '─'.repeat(width)).join('  ').trimEnd())
  for (const row of rows) {
    lines.push(columns.map((column, i) => pad(column.get(row), widths[i])).join('  ').trimEnd())
  }

  if (Array.isArray(index.epics) && index.epics.length > 0) {
    lines.push('', t('board.epics'), '')
    for (const epic of index.epics) {
      lines.push(
        `  ${epic.slug}  ${t(`status.${epic.status}`)}  ${t('board.subjectCount', { count: epic.subjects })}  ${epic.title || ''}`.trimEnd(),
      )
    }
  }
  return lines.join('\n')
}

function epicText(slug) {
  if (!index) return t('errors.archiveUnreadable', { path: archiveRoot || '?' })
  const epics = Array.isArray(index.epics) ? index.epics : []
  if (!slug) {
    if (epics.length === 0) return t('board.empty')
    return [t('board.epics'), ''].concat(epics.map((epic) => `  ${epic.slug}  ${epic.title || ''}`)).join('\n')
  }
  const epic = epics.find((candidate) => candidate.slug === slug)
  if (!epic) return `${t('board.epics')}: ${slug}?`
  const members = (index.subjects || []).filter((subject) => subject.epic === slug)
  const cells = members.map((subject) => [
    subject.id,
    t(`status.${subject.status}`),
    subject.step ? `${t(`steps.${subject.step}`)} ${subject.stepIndex}/${subject.stepTotal}` : '—',
    subject.title || '',
  ])
  const widths = [0, 1, 2].map((i) => Math.max(0, ...cells.map((row) => row[i].length)))
  const lines = [`${epic.title || epic.slug}  (${t(`status.${epic.status}`)})`, '']
  for (const row of cells) {
    lines.push(`  ${pad(row[0], widths[0])}  ${pad(row[1], widths[1])}  ${pad(row[2], widths[2])}  ${row[3]}`.trimEnd())
  }
  return lines.join('\n')
}

// ------------------------------------------------------------------ register

export function register(on) {
  on('session.start', async ($, e, next) => {
    try {
      const config = await findConfig($)
      archiveRoot = expand($, (config && config.archive) || '~/.local/share/phantom-troupe')
      await loadStrings($, config && config.owner && config.owner.language)
      await refresh($)

      $.clock.every(REFRESH_MS, async () => {
        if (await refresh($)) $.ui.invalidate('ui.render')
      })
    } catch {
      // Never keep a session from starting.
    }
    // Commands last: a refused name throws, and nothing above should be lost to it.
    try {
      await $.command.register({
        name: 'troupe-board',
        description: 'Show the Phantom Troupe board, without sending anything to Claude',
      })
      await $.command.register({
        name: 'troupe-epic',
        description: 'Show one epic and the subjects in it',
        argumentHint: '[slug]',
      })
    } catch {
      // A name already taken: the board is unavailable, the rest still works.
    }
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    try {
      if (await refresh($)) $.ui.invalidate('ui.render')
    } catch {
      // ignored on purpose
    }
    return next(e)
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    try {
      const row = bandRow($, e)
      if (row) return row
    } catch {
      // A drawing that throws is a skipped hook; draw nothing instead.
    }
    return next(e)
  })

  on('command.run', { command: 'troupe-board' }, async () => {
    return { text: boardText(), isTextDisplayOnly: true }
  })

  on('command.run', { command: 'troupe-epic' }, async ($, e) => {
    return { text: epicText((e.args || '').trim()), isTextDisplayOnly: true }
  })
}
