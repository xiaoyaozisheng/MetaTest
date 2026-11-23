/* MetaTest 本地控制台前端 —— 纯静态、离线、中英双语 */
'use strict';

/* ------------------------------------------------------------------ i18n */

const I18N = {
  zh: {
    'brand.sub': '测试有效性评估',
    'nav.overview': '概览', 'nav.run': '变异评估', 'nav.quality': '质量分析',
    'nav.selftest': '元测试自检', 'nav.project': '项目设置',
    'action.openProject': '打开项目', 'action.run': '运行评估', 'action.refresh': '刷新',
    'action.start': '开始', 'action.cancel': '关闭', 'action.back': '返回',
    'crumbs.none': '未打开项目',

    'empty.title': '先打开一个项目',
    'empty.desc': 'MetaTest 读取项目里的 metatest.yaml，对源码生成变异体并运行测试套件，衡量「测试是否真的能发现缺陷」。没有配置也可以一键初始化。',
    'empty.recent': '最近打开',
    'empty.orSelftest': '或先运行元测试自检，确认平台自身判断可信',

    'kpi.score': '变异得分', 'kpi.mutants': '变异体', 'kpi.killed': 'Killed',
    'kpi.survived': 'Survived', 'kpi.gate': '质量门禁', 'kpi.duration': '耗时',
    'kpi.killed.foot': '测试发现了变异', 'kpi.survived.foot': '测试漏测（需补断言）',
    'kpi.timeout.foot': '超时 / 等价 / 错误',
    'score.formula': 'killed ÷ (killed + survived + timeout)；等价不计入分母',
    'score.passed': '达到门禁', 'score.failed': '未达门禁', 'score.noThreshold': '未设置阈值',
    'score.empty': '暂无数据', 'score.runHint': '运行一次评估以生成得分',
    'gate.failures': '门禁失败原因',

    'dist.title': '变异体状态分布', 'dist.sub': '每个变异体的判定结果',
    'dist.skipped': '未执行',

    'files.title': '文件得分', 'files.file': '文件', 'files.score': '得分',
    'files.killed': 'Killed', 'files.survived': 'Survived', 'files.total': '总数',
    'files.low': '低分文件优先补测试',

    'engine.title': '变异引擎', 'engine.engine': '引擎', 'engine.trust': '可信度',
    'engine.exact': '语法级（AST）', 'engine.lexical': '词法级回退',

    'run.title': '变异评估', 'run.sub': '对源码生成变异体，逐个运行测试套件并判定存活/杀死',
    'run.options': '运行选项', 'run.parallel': '并行度', 'run.timeout': '单变异体超时（秒）',
    'run.incremental': '增量模式', 'run.incremental.desc': '只评估与 git 改动相关的变异体',
    'run.diffRef': 'git diff 基准', 'run.testSelection': '测试关联筛选',
    'run.testSelection.desc': '只运行覆盖变异行的测试（需要 pytest-cov）',
    'run.noQuality': '跳过质量分析', 'run.noQuality.desc': '不跑 flaky / 弱断言 / 重复测试',
    'run.flaky': '启用 flaky 检测', 'run.flaky.desc': '重复运行测试判断不稳定性（较慢）',
    'run.operators': '算子白名单', 'run.operators.help': '逗号分隔，留空使用配置（all = 全部算子）',
    'run.noCache': '禁用结果缓存', 'run.noCache.desc': '强制重新执行所有变异体',
    'run.start': '开始评估', 'run.restart': '重新运行',
    'run.trustTitle': '该配置中的命令尚未被信任',
    'run.trustDesc': '出于安全考虑，仓库内的 metatest.yaml 不能自我授权。确认下面的命令可信后才能执行：',
    'run.trustAndRun': '信任并运行',
    'run.blocked': '已有任务在运行，请等待完成。',
    'run.progress': '执行进度', 'run.queued': '排队中…',
    'run.result': '本次结果',

    'console.title': '实时日志', 'console.empty': '等待任务开始…', 'console.autoScroll': '自动滚动',

    'mutants.title': '变异体明细', 'mutants.all': '全部', 'mutants.search': '筛选文件 / 算子…',
    'mutants.operator': '算子', 'mutants.change': '变化', 'mutants.status': '状态',
    'mutants.message': '判定说明', 'mutants.none': '没有符合条件的变异体',
    'mutants.suspect': '疑似等价',

    'quality.title': '测试质量分析', 'quality.sub': 'flaky / 弱断言 / 重复测试 / 覆盖率与变异得分结合',
    'quality.run': '开始分析', 'quality.flaky': '包含 flaky 检测',
    'quality.empty': '还没有质量分析数据',
    'quality.emptyDesc': '质量分析独立于变异评估，检查测试套件本身的质量问题。',
    'quality.flakyTests': 'Flaky 测试', 'quality.weak': '弱断言', 'quality.dup': '重复测试',
    'quality.highcov': '高覆盖率低得分', 'quality.axes': '三轴质量评分', 'quality.suggestions': '可操作建议',
    'quality.noFindings': '未发现问题',

    'selftest.title': '元测试自检', 'selftest.sub': '用已知答案的基准项目验证平台自身判断是否可信',
    'selftest.cases': '基准项目', 'selftest.run': '运行自检', 'selftest.rerun': '重新自检',
    'selftest.pass': '通过', 'selftest.fail': '失败', 'selftest.skip': '跳过',
    'selftest.rate': '自检通过率', 'selftest.case': '基准项目', 'selftest.kind': '类型',
    'selftest.expected': '期望', 'selftest.actual': '实际', 'selftest.verdict': '结论',
    'selftest.untrusted': '自检失败意味着平台判断不可信：此时任何变异得分都不应作为门禁依据。',
    'selftest.empty': '尚未运行自检', 'selftest.emptyDesc': '17 个已知答案基准项目：必失败 / 必通过 / 跳过 / 超时 / 弱断言 / flaky / 变异必杀死 / 必存活 / 等价变异标记 / 词法防护。',

    'project.title': '项目设置', 'project.info': '项目信息', 'project.config': '配置',
    'project.path': '路径', 'project.language': '语言', 'project.testCmd': '测试命令',
    'project.buildCmd': '构建命令', 'project.selection': '源码 / 测试目录',
    'project.trust': '命令信任', 'project.trusted': '已信任', 'project.untrusted': '未信任',
    'project.trust': '信任此配置', 'project.revoke': '撤销信任', 'project.init': '初始化配置',
    'project.initDesc': '该目录还没有 metatest.yaml，可自动探测语言与目录结构后生成。',
    'project.save': '保存配置', 'project.saved': '配置已保存',
    'project.saveWarn': '修改配置会改变内容指纹，信任状态将失效，需要重新确认。',
    'project.reports': '报告', 'project.noReports': '还没有生成报告',
    'project.recent': '最近打开', 'project.openReport': '打开 HTML 报告',
    'project.configError': '配置解析失败',
    'interp.title': 'Python 解释器', 'interp.desc': '运行 test_cmd 使用的解释器。多 Python 环境下 PATH 上的 python 常常没装 pytest，这里可以显式指定。',
    'interp.auto': '自动探测', 'interp.use': '使用此解释器', 'interp.current': '已绑定',
    'interp.pytestOk': 'pytest 可用', 'interp.pytestMissing': 'pytest 缺失', 'interp.self': 'MetaTest 自身',
    'interp.autoMode': '自动探测中', 'interp.change': '已切换解释器',

    'modal.pickProject': '选择项目目录', 'modal.hint': '含 metatest.yaml 的目录会标记为已接入；其它目录可在打开后初始化。',
    'modal.up': '上一级', 'modal.use': '使用此目录', 'modal.noDirs': '没有子目录',

    'toast.projectOpened': '已打开项目', 'toast.runDone': '评估完成', 'toast.runFailed': '评估中止',
    'toast.saved': '已保存', 'toast.trusted': '已登记信任', 'toast.revoked': '已撤销信任',
    'toast.selftestDone': '自检完成', 'toast.qualityDone': '质量分析完成', 'toast.error': '操作失败',
    'toast.noProject': '请先打开项目',

    'axis.adequacy': '充分性 adequacy', 'axis.redundancy': '冗余 redundancy',
    'axis.maintainability': '可维护性 maintainability', 'axis.groups': '组重复用例', 'axis.weak': '个弱断言',
    'common.na': '无', 'common.yes': '是', 'common.no': '否', 'common.total': '共',
    'common.items': '项', 'common.seconds': '秒', 'common.exitCode': '退出码',
    'common.cached': '缓存', 'common.line': '行', 'common.none': '无',
  },
  en: {
    'brand.sub': 'Test effectiveness',
    'nav.overview': 'Overview', 'nav.run': 'Mutation run', 'nav.quality': 'Quality',
    'nav.selftest': 'Self-test', 'nav.project': 'Project',
    'action.openProject': 'Open project', 'action.run': 'Run', 'action.refresh': 'Refresh',
    'action.start': 'Start', 'action.cancel': 'Close', 'action.back': 'Back',
    'crumbs.none': 'No project opened',

    'empty.title': 'Open a project to begin',
    'empty.desc': 'MetaTest reads metatest.yaml, generates mutants from your sources and runs the test suite to measure whether the tests can actually detect defects. No config yet? Initialize it in one click.',
    'empty.recent': 'Recent',
    'empty.orSelftest': 'Or run the self-test first to confirm the platform judges correctly',

    'kpi.score': 'Mutation score', 'kpi.mutants': 'Mutants', 'kpi.killed': 'Killed',
    'kpi.survived': 'Survived', 'kpi.gate': 'Quality gate', 'kpi.duration': 'Duration',
    'kpi.killed.foot': 'tests detected the mutant', 'kpi.survived.foot': 'tests missed it (add assertions)',
    'kpi.timeout.foot': 'timeout / equivalent / error',
    'score.formula': 'killed ÷ (killed + survived + timeout); equivalents excluded',
    'score.passed': 'Gate passed', 'score.failed': 'Gate failed', 'score.noThreshold': 'No threshold',
    'score.empty': 'No data', 'score.runHint': 'Run an evaluation to produce a score',
    'gate.failures': 'Gate failures',

    'dist.title': 'Mutant status', 'dist.sub': 'Verdict per mutant',
    'dist.skipped': 'not run',

    'files.title': 'Score by file', 'files.file': 'File', 'files.score': 'Score',
    'files.killed': 'Killed', 'files.survived': 'Survived', 'files.total': 'Total',
    'files.low': 'Start with the lowest-scoring files',

    'engine.title': 'Mutation engine', 'engine.engine': 'Engine', 'engine.trust': 'Precision',
    'engine.exact': 'syntactic (AST)', 'engine.lexical': 'lexical fallback',

    'run.title': 'Mutation run', 'run.sub': 'Generate mutants, run the suite for each, classify killed/survived',
    'run.options': 'Options', 'run.parallel': 'Parallelism', 'run.timeout': 'Timeout per mutant (s)',
    'run.incremental': 'Incremental', 'run.incremental.desc': 'Only mutants related to git changes',
    'run.diffRef': 'git diff base', 'run.testSelection': 'Test selection',
    'run.testSelection.desc': 'Run only tests covering the mutated line (needs pytest-cov)',
    'run.noQuality': 'Skip quality analysis', 'run.noQuality.desc': 'No flaky / weak assertion / duplicates',
    'run.flaky': 'Detect flaky tests', 'run.flaky.desc': 'Repeated runs to detect instability (slower)',
    'run.operators': 'Operator whitelist', 'run.operators.help': 'Comma separated; empty uses config (all = every operator)',
    'run.noCache': 'Disable cache', 'run.noCache.desc': 'Re-execute every mutant',
    'run.start': 'Start run', 'run.restart': 'Run again',
    'run.trustTitle': 'Commands in this config are not trusted',
    'run.trustDesc': 'A repository cannot authorize itself. Confirm the commands below before execution:',
    'run.trustAndRun': 'Trust and run',
    'run.blocked': 'A job is already running, please wait.',
    'run.progress': 'Progress', 'run.queued': 'Queued…',
    'run.result': 'This run',

    'console.title': 'Live log', 'console.empty': 'Waiting for the job…', 'console.autoScroll': 'Auto-scroll',

    'mutants.title': 'Mutants', 'mutants.all': 'All', 'mutants.search': 'Filter by file / operator…',
    'mutants.operator': 'Operator', 'mutants.change': 'Change', 'mutants.status': 'Status',
    'mutants.message': 'Verdict', 'mutants.none': 'No mutants match the filter',
    'mutants.suspect': 'suspect equivalent',

    'quality.title': 'Test quality', 'quality.sub': 'flaky / weak assertions / duplicates / coverage vs mutation score',
    'quality.run': 'Analyze', 'quality.flaky': 'Include flaky detection',
    'quality.empty': 'No quality data yet',
    'quality.emptyDesc': 'Quality analysis is independent of the mutation run: it inspects the test suite itself.',
    'quality.flakyTests': 'Flaky tests', 'quality.weak': 'Weak assertions', 'quality.dup': 'Duplicate tests',
    'quality.highcov': 'High coverage, low score', 'quality.axes': 'Three-axis quality', 'quality.suggestions': 'Actions',
    'quality.noFindings': 'No findings',

    'selftest.title': 'Meta self-test', 'selftest.sub': 'Known-answer fixtures verify the platform\'s own judgments',
    'selftest.cases': 'Fixtures', 'selftest.run': 'Run self-test', 'selftest.rerun': 'Run again',
    'selftest.pass': 'Passed', 'selftest.fail': 'Failed', 'selftest.skip': 'Skipped',
    'selftest.rate': 'Pass rate', 'selftest.case': 'Fixture', 'selftest.kind': 'Kind',
    'selftest.expected': 'Expected', 'selftest.actual': 'Actual', 'selftest.verdict': 'Verdict',
    'selftest.untrusted': 'A failing self-test means the platform itself is unreliable: no mutation score should gate CI.',
    'selftest.empty': 'Self-test not run yet', 'selftest.emptyDesc': '17 known-answer fixtures: must-fail / must-pass / skipped / timeout / weak assertion / flaky / mutant must be killed / must survive / manual equivalent / lexical guard.',

    'project.title': 'Project', 'project.info': 'Project info', 'project.config': 'Configuration',
    'project.path': 'Path', 'project.language': 'Language', 'project.testCmd': 'Test command',
    'project.buildCmd': 'Build command', 'project.selection': 'Source / test roots',
    'project.trust': 'Command trust', 'project.trusted': 'Trusted', 'project.untrusted': 'Not trusted',
    'project.trustAction': 'Trust this config', 'project.revoke': 'Revoke trust', 'project.init': 'Initialize config',
    'project.initDesc': 'No metatest.yaml here yet. MetaTest can detect the language and layout and create one.',
    'project.save': 'Save config', 'project.saved': 'Configuration saved',
    'project.saveWarn': 'Editing the config changes its fingerprint, so trust is revoked and must be confirmed again.',
    'project.reports': 'Reports', 'project.noReports': 'No report generated yet',
    'project.recent': 'Recent projects', 'project.openReport': 'Open HTML report',
    'project.configError': 'Config parse error',
    'interp.title': 'Python interpreter', 'interp.desc': 'Interpreter used to run test_cmd. With multiple Pythons, the one on PATH often lacks pytest — pick explicitly here.',
    'interp.auto': 'Auto-detect', 'interp.use': 'Use this interpreter', 'interp.current': 'assigned',
    'interp.pytestOk': 'pytest ok', 'interp.pytestMissing': 'pytest missing', 'interp.self': 'MetaTest itself',
    'interp.autoMode': 'auto-detecting', 'interp.change': 'Interpreter updated',

    'modal.pickProject': 'Choose a project directory', 'modal.hint': 'Directories with metatest.yaml are marked as onboarded; others can be initialized after opening.',
    'modal.up': 'Up', 'modal.use': 'Use this directory', 'modal.noDirs': 'No subdirectories',

    'toast.projectOpened': 'Project opened', 'toast.runDone': 'Run finished', 'toast.runFailed': 'Run aborted',
    'toast.saved': 'Saved', 'toast.trusted': 'Trust registered', 'toast.revoked': 'Trust revoked',
    'toast.selftestDone': 'Self-test finished', 'toast.qualityDone': 'Quality analysis finished', 'toast.error': 'Failed',
    'toast.noProject': 'Open a project first',

    'axis.adequacy': 'Adequacy', 'axis.redundancy': 'Redundancy',
    'axis.maintainability': 'Maintainability', 'axis.groups': 'duplicate groups', 'axis.weak': 'weak assertions',
    'common.na': 'n/a', 'common.yes': 'yes', 'common.no': 'no', 'common.total': 'total',
    'common.items': 'items', 'common.seconds': 's', 'common.exitCode': 'exit',
    'common.cached': 'cached', 'common.line': 'line', 'common.none': 'none',
  },
};

const STATUS = {
  killed:     { zh: '杀死', en: 'Killed', cls: 'ok', key: 'k' },
  survived:   { zh: '漏测', en: 'Survived', cls: 'bad', key: 's' },
  timeout:    { zh: '超时', en: 'Timeout', cls: 'warn', key: 't' },
  equivalent: { zh: '等价', en: 'Equivalent', cls: 'info', key: 'e' },
  error:      { zh: '错误', en: 'Error', cls: '', key: 'x' },
  not_run:    { zh: '未执行', en: 'Not run', cls: '', key: 'x' },
};

/* ------------------------------------------------------------------ 状态 */

const state = {
  lang: localStorage.getItem('mt.lang') || 'zh',
  theme: localStorage.getItem('mt.theme') || 'light',
  meta: null,
  project: null,
  results: null,
  quality: null,
  selftest: null,
  selftestCases: [],
  interpreters: null,
  interpLoading: false,
  interpFailed: null,
  job: null,
  jobKind: null,
  view: 'overview',
  logIndex: 0,
  logs: [],
  mutantFilter: 'all',
  mutantSearch: '',
  browsing: { path: null, parent: null, dirs: [], roots: [] },
  runnerBusy: false,
};

const t = (key, vars) => {
  let s = (I18N[state.lang] && I18N[state.lang][key]) ?? I18N.zh[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll('{' + k + '}', v);
  return s;
};

/* ------------------------------------------------------------------ 工具 */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function esc(v) {
  return String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function fmtPct(v, digits = 1) {
  if (v === null || v === undefined) return '—';
  return Number(v).toFixed(digits) + '%';
}

function fmtDur(sec) {
  if (sec === null || sec === undefined) return '—';
  if (sec < 60) return sec.toFixed(1) + 's';
  const m = Math.floor(sec / 60);
  return `${m}m ${Math.round(sec - m * 60)}s`;
}

function fmtTime(epoch) {
  if (!epoch) return '—';
  const d = new Date(epoch * 1000);
  const pad = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function shortPath(p, max = 46) {
  if (!p) return '';
  const s = String(p).replace(/\\/g, '/');
  return s.length <= max ? s : '…' + s.slice(-(max - 1));
}

async function api(path, opts = {}) {
  const init = { method: opts.method || 'GET', headers: {} };
  if (init.method !== 'GET') {
    init.headers['Content-Type'] = 'application/json';
    init.headers['X-Metatest-Client'] = 'web';
    init.body = JSON.stringify(opts.body || {});
  }
  const res = await fetch(path, init);
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = { error: text }; }
  if (!res.ok) {
    const err = new Error((data && (data.error || data.message)) || `HTTP ${res.status}`);
    err.code = data && data.code;
    err.status = res.status;
    throw err;
  }
  return data;
}

function toast(msg, kind = '') {
  const wrap = $('#toasts');
  const node = document.createElement('div');
  node.className = 'toast ' + kind;
  node.textContent = msg;
  wrap.appendChild(node);
  setTimeout(() => { node.style.opacity = '0'; node.style.transition = 'opacity .25s'; }, 4200);
  setTimeout(() => node.remove(), 4600);
}

function svgIcon(name) {
  const paths = {
    folder: '<path d="M2 5h6l1.5 2H18v9H2z"/>',
    play: '<path d="M7 4l9 6-9 6z"/>',
    refresh: '<path d="M10 3a7 7 0 107 7h-2a5 5 0 11-5-5v3l4-3.5L10 1z"/>',
    check: '<path d="M8.2 13.4L4 9.2l1.4-1.4 2.8 2.8 6-6L15.6 6z"/>',
    alert: '<path d="M10 2l8 15H2zM9 8h2v4H9zm0 5h2v2H9z"/>',
    info: '<path d="M10 2a8 8 0 100 16 8 8 0 000-16zm-1 4h2v2H9zm0 3h2v5H9z"/>',
    bulb: '<path d="M10 2a5 5 0 00-3 9v2h6v-2a5 5 0 00-3-9zM8 15h4v2H8z"/>',
    file: '<path d="M4 2h8l4 4v12H4z"/>',
  };
  return `<svg viewBox="0 0 20 20" class="ico" aria-hidden="true">${paths[name] || ''}</svg>`;
}

/* 引擎与门禁信息由 CLI 产出（中文）；英文界面下按模式翻译常见行，未命中保持原文 */
const TEXT_I18N = [
  [/^\[init\] 项目 (.+?)（(.+?)）· 算子 (\d+) 个 · 并行 (\d+)$/,
    m => `[init] Project ${m[1]} (${m[2]}) · ${m[3]} operators · parallelism ${m[4]}`],
  [/^\[init\] 生成变异体 (\d+) 个$/, m => `[init] Generated ${m[1]} mutants`],
  [/^\[init\] 变异策略: (.+?)（链: (.+?)）$/, m => `[init] Strategy: ${m[1]} (chain: ${m[2]})`],
  [/^\[baseline\] 运行基线测试: (.+)$/, m => `[baseline] Running baseline: ${m[1]}`],
  [/^\[baseline\] (\w+)（tests=(\d+) failures=(\d+) errors=(\d+) skipped=(\d+)，([\d.]+)s）$/,
    m => `[baseline] ${m[1]} (tests=${m[2]} failures=${m[3]} errors=${m[4]} skipped=${m[5]}, ${m[6]}s)`],
  [/^\[run\] 变异体 (\d+) 个；待执行 (\d+)（并行 (\d+)，超时 ([\d.]+)s）$/,
    m => `[run] ${m[1]} mutants, ${m[2]} to execute (parallel ${m[3]}, timeout ${m[4]}s)`],
  [/^变异体 (\d+) \| killed (\d+) \| survived (\d+) \| timeout (\d+) \| equivalent (\d+) \| error (\d+)$/,
    m => `Mutants ${m[1]} | killed ${m[2]} | survived ${m[3]} | timeout ${m[4]} | equivalent ${m[5]} | error ${m[6]}`],
  [/^变异得分: (—|[\d.]+%?)（门禁阈值 ([\d.]+)% → (.+?)）$/, m => `Mutation score: ${m[1]} (gate ${m[2]}% → ${m[3]})`],
  [/^变异得分: (—|[\d.]+%?)$/, m => `Mutation score: ${m[1]}`],
  [/^报告: (.+)$/, m => `Report: ${m[1]}`],
  [/^变异得分 ([\d.]+)% 低于门禁阈值 ([\d.]+)%$/, m => `Mutation score ${m[1]}% below gate threshold ${m[2]}%`],
  [/^存在 (\d+) 个漏测变异（fail_on_survived）$/, m => `${m[1]} survived mutants (fail_on_survived)`],
  [/^变异得分无法计算（无可计分变异体），门禁阈值 ([\d.]+)%$/, m => `Mutation score not computable (no scorable mutants); threshold ${m[1]}%`],
  [/^flaky 测试 (\d+) 个，超过上限 (\d+)$/, m => `${m[1]} flaky tests exceed limit ${m[2]}`],
  [/^弱断言测试 (\d+) 个，超过上限 (\d+)$/, m => `${m[1]} weak-assertion tests exceed limit ${m[2]}`],
  [/^元测试自检: 通过 (\d+) · 失败 (\d+) · 跳过\(环境缺失\) (\d+)$/,
    m => `Self-test: passed ${m[1]} · failed ${m[2]} · skipped ${m[3]}`],
  [/^自检通过率: (\d+)%（已执行用例，跳过用例不计入）$/, m => `Self-test pass rate: ${m[1]}% (executed cases only)`],
  [/^\[selftest\] (PASS|FAIL|SKIP)\s+(\S+): expected=(\S+) actual=(\S+)(?: \((.*)\))?$/,
    m => `[selftest] ${m[1]} ${m[2]}: expected=${m[3]} actual=${m[4]}${m[5] ? ' (' + m[5] + ')' : ''}`],
];

function localizeText(text) {
  if (state.lang === 'zh' || !text) return text;
  for (const [re, fn] of TEXT_I18N) {
    const m = text.match(re);
    if (m) return fn(m);
  }
  return text;
}

function ring(score, size = 104) {
  const pct = score === null || score === undefined ? 0 : Math.max(0, Math.min(100, score));
  const r = 48, c = 2 * Math.PI * r;
  const off = c * (1 - pct / 100);
  const color = score === null || score === undefined
    ? 'var(--line-strong)'
    : pct >= 80 ? 'var(--ok)' : pct >= 60 ? 'var(--warn)' : 'var(--bad)';
  return `
  <svg class="ring" viewBox="0 0 116 116" width="${size}" height="${size}" role="img">
    <circle class="track" cx="58" cy="58" r="${r}" fill="none" stroke-width="10"/>
    <circle class="arc" cx="58" cy="58" r="${r}" fill="none" stroke="${color}" stroke-width="10"
      stroke-linecap="round" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${off.toFixed(1)}"
      transform="rotate(-90 58 58)"/>
    <text x="58" y="57" text-anchor="middle" class="ring-label">${score === null || score === undefined ? '—' : pct.toFixed(1)}</text>
    <text x="58" y="73" text-anchor="middle" class="ring-sub">SCORE %</text>
  </svg>`;
}

function statusChip(status) {
  const meta = STATUS[status] || STATUS.not_run;
  const label = state.lang === 'zh' ? meta.zh : meta.en;
  return `<span class="chip ${meta.cls}">${esc(label)}</span>`;
}

function distBar(summary) {
  const parts = [
    ['k', summary.killed], ['s', summary.survived], ['t', summary.timeout],
    ['e', summary.equivalent], ['x', summary.error],
  ];
  const total = parts.reduce((a, [, v]) => a + (v || 0), 0) || 1;
  return parts.map(([cls, v]) => v ? `<span class="${cls}" style="width:${(v / total * 100).toFixed(2)}%"></span>` : '').join('');
}

function legend(summary) {
  const items = [
    ['k', 'var(--ok)', state.lang === 'zh' ? 'Killed 杀死' : 'Killed', summary.killed],
    ['s', 'var(--bad)', state.lang === 'zh' ? 'Survived 漏测' : 'Survived', summary.survived],
    ['t', 'var(--warn)', state.lang === 'zh' ? 'Timeout 超时' : 'Timeout', summary.timeout],
    ['e', 'var(--info)', state.lang === 'zh' ? 'Equivalent 等价' : 'Equivalent', summary.equivalent],
    ['x', 'var(--neutral)', state.lang === 'zh' ? 'Error 错误' : 'Error', summary.error],
  ];
  return items.map(([, color, label, n]) => `
    <div class="item"><span class="sw" style="background:${color}"></span>
      <span>${esc(label)}</span><span class="num">${n ?? 0}</span></div>`).join('');
}

/* ------------------------------------------------------------------ 渲染入口 */

function applyStaticI18n() {
  document.querySelectorAll('[data-i18n]').forEach(node => {
    node.textContent = t(node.dataset.i18n);
  });
  document.title = 'MetaTest · ' + t('brand.sub');
  const modalTitle = $('#modalTitle');
  if (modalTitle) modalTitle.textContent = t('modal.pickProject');
}

function render() {
  document.documentElement.dataset.theme = state.theme;
  document.documentElement.lang = state.lang === 'zh' ? 'zh-CN' : 'en';
  applyStaticI18n();
  $('#langSwitch').querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.lang === state.lang));
  $('#version').textContent = state.meta ? 'v' + state.meta.version : '';
  $$('#nav .nav-item').forEach(b => b.classList.toggle('active', b.dataset.view === state.view));
  renderCrumbs();
  renderSideProject();
  const view = $('#view');
  const renderers = {
    overview: viewOverview, run: viewRun, quality: viewQuality,
    selftest: viewSelftest, project: viewProject,
  };
  view.innerHTML = (renderers[state.view] || viewOverview)();
  bindView();
  restoreConsole();
  if (state.view === 'project' && state.project && state.project.language === 'python') {
    loadInterpreters(state.project.path);
  }
}

function renderCrumbs() {
  const box = $('#crumbs');
  if (!state.project) {
    box.innerHTML = `<span class="crumb-muted">${esc(t('crumbs.none'))}</span>`;
    return;
  }
  const p = state.project;
  box.innerHTML = `
    <span style="font-weight:600">${esc(p.name)}</span>
    <span class="chip ${p.has_config ? 'ok' : 'warn'}">${p.has_config ? 'metatest.yaml' : 'no config'}</span>
    <span class="chip outline">${esc(p.language)}</span>
    <span class="crumb-path" title="${esc(p.path)}">${esc(shortPath(p.path, 62))}</span>`;
}

function renderSideProject() {
  const box = $('#sideProject');
  if (!state.project) { box.innerHTML = ''; return; }
  const p = state.project;
  box.innerHTML = `
    <div class="proj-chip">
      <div class="name" title="${esc(p.name)}">${esc(p.name)}</div>
      <div class="path" title="${esc(p.path)}">${esc(shortPath(p.path, 26))}</div>
      <div class="chips">
        <span class="chip ${p.trusted ? 'ok' : 'warn'}">${p.trusted ? esc(t('project.trusted')) : esc(t('project.untrusted'))}</span>
        ${p.last_report ? `<span class="chip outline">${fmtPct(p.last_report.score)}</span>` : ''}
      </div>
    </div>`;
}

/* ------------------------------------------------------------------ 概览 */

function viewOverview() {
  if (!state.project) return emptyState();
  const p = state.project;
  const r = state.results;
  const summary = r ? r.summary : (p.last_report ? {
    total: p.last_report.total, killed: p.last_report.killed, survived: p.last_report.survived,
    timeout: 0, equivalent: 0, error: p.last_report.error,
    mutation_score_percent: p.last_report.score, duration_sec: p.last_report.duration_sec,
  } : null);

  if (!summary) {
    return `
      <div class="stack">
        <div>
          <div class="section-title">${esc(p.name)}</div>
          <div class="section-desc">${esc(t('score.runHint'))}</div>
        </div>
        ${configIssueBanner()}
        <div class="empty">
          ${svgIcon('play')}
          <div class="title">${esc(t('score.empty'))}</div>
          <div class="desc">${esc(t('empty.desc'))}</div>
          <button class="btn primary" data-act="goto-run">${svgIcon('play')}${esc(t('run.start'))}</button>
        </div>
      </div>`;
  }

  const gate = (r && r.gate) || (p.last_report && p.last_report.gate) || null;
  const score = summary.mutation_score_percent;
  const gateOk = gate ? gate.passed : null;
  const files = r ? Object.entries(r.file_scores || {}) : [];
  files.sort((a, b) => (a[1].score ?? 1) - (b[1].score ?? 1));
  const engines = r ? Object.entries(r.engine_scores || {}) : [];

  return `
    <div class="stack">
      <div>
        <div class="section-title">${esc(p.name)} · ${esc(t('nav.overview'))}</div>
        <div class="section-desc">${summary.total} ${esc(t('kpi.mutants'))} · ${esc(t('kpi.duration'))} ${fmtDur(summary.duration_sec)}
          ${r && r.generated_at ? ' · ' + esc(r.generated_at) : ''}</div>
      </div>
      ${configIssueBanner()}

      <div class="kpis">
        <div class="kpi score">
          <div class="score-block">
            ${ring(score)}
            <div class="score-meta">
              <div class="kpi-label">${esc(t('kpi.score'))}</div>
              <div class="verdict" style="color:${gateOk === false ? 'var(--bad)' : gateOk ? 'var(--ok)' : 'var(--text)'}">
                ${gateOk === null ? esc(t('score.noThreshold')) : gateOk ? esc(t('score.passed')) : esc(t('score.failed'))}
              </div>
              <div class="formula">${esc(t('score.formula'))}</div>
            </div>
          </div>
        </div>
        <div class="kpi">
          <div class="kpi-label">${esc(t('kpi.mutants'))}</div>
          <div class="kpi-value">${summary.total}</div>
          <div class="kpi-foot">${esc(t('kpi.duration'))} ${fmtDur(summary.duration_sec)}</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">${esc(t('kpi.killed'))}</div>
          <div class="kpi-value" style="color:var(--ok)">${summary.killed}</div>
          <div class="kpi-foot">${esc(t('kpi.killed.foot'))}</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">${esc(t('kpi.survived'))}</div>
          <div class="kpi-value" style="color:var(--bad)">${summary.survived}</div>
          <div class="kpi-foot">${esc(t('kpi.survived.foot'))}</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">${esc(t('kpi.gate'))}</div>
          <div class="kpi-value" style="font-size:20px;color:${gateOk === false ? 'var(--bad)' : gateOk ? 'var(--ok)' : 'var(--text-2)'}">
            ${gateOk === null ? '—' : gateOk ? esc(t('score.passed')) : esc(t('score.failed'))}
          </div>
          <div class="kpi-foot">${gate && gate.threshold != null ? 'threshold ' + gate.threshold + '%' : esc(t('score.noThreshold'))}</div>
        </div>
      </div>

      ${gate && gate.failures && gate.failures.length ? `
      <div class="banner bad">${svgIcon('alert')}
        <div><b>${esc(t('gate.failures'))}</b><br>${gate.failures.map(f => esc(localizeText(f))).join('<br>')}</div>
      </div>` : ''}

      <div class="grid cols-2">
        <div class="card">
          <div class="card-head">
            <div><div class="card-title">${esc(t('dist.title'))}</div>
              <div class="card-sub">${esc(t('dist.sub'))}</div></div>
            <span class="chip outline">${summary.total} ${esc(t('common.items'))}</span>
          </div>
          <div class="card-body">
            <div class="dist">${distBar(summary)}</div>
            <div class="legend">${legend(summary)}</div>
          </div>
        </div>

        <div class="card">
          <div class="card-head">
            <div class="card-title">${esc(t('project.info'))}</div>
            <button class="btn small ghost" data-act="goto-project">${esc(t('nav.project'))}</button>
          </div>
          <div class="card-body">
            <dl class="kv">
              <dt>${esc(t('project.testCmd'))}</dt><dd>${esc(p.config ? p.config.test_cmd : '—')}</dd>
              <dt>${esc(t('project.selection'))}</dt>
              <dd>${esc(p.config ? p.config.source_roots.join(', ') + ' / ' + p.config.test_roots.join(', ') : '—')}</dd>
              <dt>${esc(t('kpi.duration'))}</dt><dd>${fmtDur(summary.duration_sec)}</dd>
              ${r && r.baseline ? `<dt>baseline</dt><dd>${esc(r.baseline.outcome)} · tests ${r.baseline.tests}
                · fail ${r.baseline.failures} · skip ${r.baseline.skipped}</dd>` : ''}
              ${r && r.incremental ? `<dt>incremental</dt><dd>${r.incremental.kept}/${r.incremental.total}
                · ${esc(r.incremental.source || '')}</dd>` : ''}
              ${r && r.test_selection ? `<dt>test selection</dt><dd>${r.test_selection.tests} tests
                · ${r.test_selection.build_sec}s</dd>` : ''}
            </dl>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-head">
          <div><div class="card-title">${esc(t('files.title'))}</div>
            <div class="card-sub">${esc(t('files.low'))}</div></div>
          ${reportLinks()}
        </div>
        <div class="card-body tight">
          <div class="table-wrap">
            <table class="table">
              <thead><tr>
                <th>${esc(t('files.file'))}</th>
                <th class="right">${esc(t('files.score'))}</th>
                <th class="right">${esc(t('files.killed'))}</th>
                <th class="right">${esc(t('files.survived'))}</th>
                <th style="width:140px"></th>
              </tr></thead>
              <tbody>
                ${files.map(([path, info]) => `
                  <tr>
                    <td class="loc" title="${esc(path)}">${esc(shortPath(path, 60))}</td>
                    <td class="num" style="color:${scoreColor(info.score)}">${fmtPct(info.score === null ? null : info.score * 100)}</td>
                    <td class="num">${info.killed}</td>
                    <td class="num" style="color:${info.survived ? 'var(--bad)' : 'inherit'}">${info.survived}</td>
                    <td><div class="bar-mini"><div style="width:${((info.score ?? 0) * 100).toFixed(1)}%;background:${scoreColor(info.score)}"></div></div></td>
                  </tr>`).join('') || `<tr><td colspan="5" class="muted" style="padding:16px">${esc(t('common.none'))}</td></tr>`}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      ${engines.length > 1 ? `
      <div class="card">
        <div class="card-head"><div class="card-title">${esc(t('engine.title'))}</div></div>
        <div class="card-body tight">
          <table class="table">
            <thead><tr><th>${esc(t('engine.engine'))}</th><th class="right">${esc(t('kpi.mutants'))}</th>
              <th class="right">${esc(t('files.score'))}</th><th>${esc(t('engine.trust'))}</th></tr></thead>
            <tbody>${engines.map(([name, g]) => `
              <tr><td class="mono">${esc(name)}</td><td class="num">${g.total}</td>
              <td class="num">${fmtPct(g.score === null ? null : g.score * 100)}</td>
              <td>${name === 'ast' || name === 'tree_sitter'
                ? `<span class="chip ok">${esc(t('engine.exact'))}</span>`
                : `<span class="chip warn">${esc(t('engine.lexical'))}</span>`}</td></tr>`).join('')}
            </tbody>
          </table>
        </div>
      </div>` : ''}
    </div>`;
}

function emptyState() {
  const recent = (state.meta && state.meta.recent) || [];
  return `
    <div class="stack">
      <div class="empty">
        ${svgIcon('folder')}
        <div class="title">${esc(t('empty.title'))}</div>
        <div class="desc">${esc(t('empty.desc'))}</div>
        <div class="row-gap">
          <button class="btn primary" data-act="open-project">${svgIcon('folder')}${esc(t('action.openProject'))}</button>
          <button class="btn" data-act="goto-selftest">${svgIcon('check')}${esc(t('nav.selftest'))}</button>
        </div>
      </div>
      ${recent.length ? `
      <div class="card">
        <div class="card-head"><div class="card-title">${esc(t('empty.recent'))}</div></div>
        <div class="card-body tight">
          ${recent.map(p => `
            <div class="browser"><div class="dir" data-recent="${esc(p)}">
              ${svgIcon('folder')}<span class="mono small">${esc(p)}</span>
              <span class="pathhint">${esc(t('action.openProject'))} →</span>
            </div></div>`).join('')}
        </div>
      </div>` : `<div class="small muted" style="text-align:center">${esc(t('empty.orSelftest'))}</div>`}
    </div>`;
}

function configIssueBanner() {
  if (!state.project) return '';
  if (state.project.config_error) {
    return `<div class="banner bad">${svgIcon('alert')}<div><b>${esc(t('project.configError'))}</b><br>
      <span class="mono small">${esc(state.project.config_error)}</span></div></div>`;
  }
  if (!state.project.has_config) {
    return `<div class="banner warn">${svgIcon('alert')}<div>${esc(t('project.initDesc'))}
      <button class="btn small" style="margin-left:8px" data-act="init-config">${esc(t('project.init'))}</button></div></div>`;
  }
  return '';
}

function reportLinks() {
  const p = state.project;
  const paths = state.results && state.results.paths;
  if (!p || !p.last_report) return '';
  const links = p.last_report.paths || {};
  return `<div class="row-gap">
    ${links.html ? `<a class="btn small ghost" href="/api/report?path=${encodeURIComponent(p.path)}&file=report.html" target="_blank">HTML</a>` : ''}
    ${links.json ? `<a class="btn small ghost" href="/api/report?path=${encodeURIComponent(p.path)}&file=results.json" target="_blank">JSON</a>` : ''}
    ${links.junit ? `<a class="btn small ghost" href="/api/report?path=${encodeURIComponent(p.path)}&file=mutation_junit.xml" target="_blank">JUnit</a>` : ''}
  </div>`;
}

function scoreColor(score) {
  if (score === null || score === undefined) return 'var(--muted)';
  const p = score * 100;
  return p >= 80 ? 'var(--ok)' : p >= 60 ? 'var(--warn)' : 'var(--bad)';
}

/* ------------------------------------------------------------------ 运行页 */

function viewRun() {
  if (!state.project) return emptyState();
  const p = state.project;
  const cfg = p.config;
  const busy = state.runnerBusy;
  const opts = state.runOptions || {};
  const needsTrust = p.has_config && !p.trusted;

  return `
    <div class="stack">
      <div>
        <div class="section-title">${esc(t('run.title'))}</div>
        <div class="section-desc">${esc(t('run.sub'))}</div>
      </div>
      ${configIssueBanner()}
      ${needsTrust ? `
        <div class="banner warn">${svgIcon('alert')}
          <div style="flex:1">
            <b>${esc(t('run.trustTitle'))}</b><br>${esc(t('run.trustDesc'))}
            <div class="mono small" style="margin-top:6px">
              build: ${esc(cfg ? cfg.build_cmd || '—' : '—')}<br>
              test: ${esc(cfg ? cfg.test_cmd : '—')}
            </div>
            <div class="row-gap" style="margin-top:10px">
              <button class="btn primary small" data-act="trust-run">${esc(t('run.trustAndRun'))}</button>
              <button class="btn small" data-act="trust-only">${esc(t('project.trustAction'))}</button>
            </div>
          </div>
        </div>` : ''}

      <div class="grid cols-2">
        <div class="card">
          <div class="card-head"><div class="card-title">${esc(t('run.options'))}</div></div>
          <div class="card-body">
            <div class="form">
              <div class="grid cols-2">
                <div class="field">
                  <label>${esc(t('run.parallel'))}</label>
                  <input class="input" type="number" min="1" max="32" id="optParallel"
                    value="${esc(opts.parallel ?? (cfg ? cfg.parallelism : 4))}">
                </div>
                <div class="field">
                  <label>${esc(t('run.timeout'))}</label>
                  <input class="input" type="number" min="5" max="3600" id="optTimeout"
                    value="${esc(opts.timeout ?? (cfg ? cfg.timeout_sec : 120))}">
                </div>
              </div>
              <div class="field">
                <label>${esc(t('run.operators'))}</label>
                <input class="input mono" id="optOperators" placeholder="all" value="${esc(opts.operators || '')}">
                <div class="help">${esc(t('run.operators.help'))}</div>
              </div>
              <label class="check"><input type="checkbox" id="optIncremental" ${opts.incremental ? 'checked' : ''}>
                <span>${esc(t('run.incremental'))}<span class="desc"> · ${esc(t('run.incremental.desc'))}</span></span></label>
              <div class="field">
                <label>${esc(t('run.diffRef'))}</label>
                <input class="input mono" id="optDiffRef" placeholder="HEAD" value="${esc(opts.diffRef || '')}">
              </div>
              <label class="check"><input type="checkbox" id="optTestSelection" ${opts.testSelection ? 'checked' : ''}>
                <span>${esc(t('run.testSelection'))}<span class="desc"> · ${esc(t('run.testSelection.desc'))}</span></span></label>
              <label class="check"><input type="checkbox" id="optFlaky" ${opts.flaky ? 'checked' : ''}>
                <span>${esc(t('run.flaky'))}<span class="desc"> · ${esc(t('run.flaky.desc'))}</span></span></label>
              <label class="check"><input type="checkbox" id="optNoQuality" ${opts.noQuality ? 'checked' : ''}>
                <span>${esc(t('run.noQuality'))}<span class="desc"> · ${esc(t('run.noQuality.desc'))}</span></span></label>
              <label class="check"><input type="checkbox" id="optNoCache" ${opts.noCache ? 'checked' : ''}>
                <span>${esc(t('run.noCache'))}<span class="desc"> · ${esc(t('run.noCache.desc'))}</span></span></label>
              <div class="row-gap">
                <button class="btn primary" data-act="start-run" ${busy ? 'disabled' : ''}>
                  ${svgIcon('play')}${esc(busy ? t('run.queued') : t('run.start'))}</button>
                ${busy ? `<span class="small muted">${esc(t('run.blocked'))}</span>` : ''}
              </div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-head">
            <div class="card-title">${esc(t('console.title'))}</div>
            ${jobChip()}
          </div>
          <div class="card-body">
            ${progressBar()}
            <div class="console" id="console" style="margin-top:12px"></div>
          </div>
        </div>
      </div>

      ${state.results ? runResultCard(state.results) : ''}
    </div>`;
}

function runResultCard(r) {
  const summary = r.summary;
  const survivors = (r.mutants || []).filter(m => m.status === 'survived');
  return `
    <div class="card">
      <div class="card-head">
        <div><div class="card-title">${esc(t('run.result'))}</div>
          <div class="card-sub">${esc(t('kpi.score'))} ${fmtPct(summary.mutation_score_percent)}
            · ${esc(t('kpi.duration'))} ${fmtDur(summary.duration_sec)}</div></div>
        ${reportLinks()}
      </div>
      <div class="card-body">
        <div class="dist" style="margin-bottom:10px">${distBar(summary)}</div>
        <div class="legend">${legend(summary)}</div>
      </div>
      <div class="card-body tight" style="border-top:1px solid var(--line)">
        ${mutantTable(r, survivors, 'survived')}
      </div>
    </div>`;
}

/* 变异体表格（带状态筛选与搜索） */
function mutantTable(r, mutants, initialFilter = 'all') {
  const all = r.mutants || [];
  const counts = { all: all.length };
  all.forEach(m => { counts[m.status] = (counts[m.status] || 0) + 1; });
  const filter = state.mutantFilter || initialFilter;
  const q = (state.mutantSearch || '').toLowerCase();
  const rows = all.filter(m => (filter === 'all' || m.status === filter)
    && (!q || (m.path + ' ' + m.operator + ' ' + (m.message || '')).toLowerCase().includes(q)));

  const filterBtn = (key, label) => `
    <button class="filter-btn ${filter === key ? 'on' : ''}" data-filter="${key}">
      ${esc(label)}<span class="n">${counts[key] || 0}</span></button>`;

  return `
    <div class="card-head" style="border-bottom:1px solid var(--line)">
      <div class="filters">
        ${filterBtn('all', t('mutants.all'))}
        ${filterBtn('survived', state.lang === 'zh' ? '漏测' : 'Survived')}
        ${filterBtn('killed', state.lang === 'zh' ? '杀死' : 'Killed')}
        ${filterBtn('timeout', state.lang === 'zh' ? '超时' : 'Timeout')}
        ${filterBtn('equivalent', state.lang === 'zh' ? '等价' : 'Equivalent')}
        ${filterBtn('error', state.lang === 'zh' ? '错误' : 'Error')}
      </div>
      <input class="search" id="mutantSearch" placeholder="${esc(t('mutants.search'))}" value="${esc(state.mutantSearch)}">
    </div>
    <div class="table-wrap">
      <table class="table">
        <thead><tr>
          <th style="width:34px"></th>
          <th>${esc(t('files.file'))}</th>
          <th>${esc(t('mutants.operator'))}</th>
          <th>${esc(t('mutants.change'))}</th>
          <th class="right">${esc(t('kpi.duration'))}</th>
          <th>${esc(t('mutants.message'))}</th>
        </tr></thead>
        <tbody>
          ${rows.slice(0, 400).map(m => `
            <tr>
              <td>${statusChip(m.status)}</td>
              <td class="loc">${esc(m.path)}:${m.line}</td>
              <td class="code">${esc(m.operator)}</td>
              <td class="code"><b>${esc(m.original)}</b> → <i>${esc(m.mutated)}</i></td>
              <td class="num">${m.duration_sec ? m.duration_sec.toFixed(2) + 's' : '—'}</td>
              <td class="trunc" title="${esc(m.message)}">${esc(m.message || '')}
                ${m.suspect_equivalent ? `<span class="chip warn" style="margin-left:4px">${esc(t('mutants.suspect'))}</span>` : ''}
                ${m.cached ? `<span class="chip outline" style="margin-left:4px">${esc(t('common.cached'))}</span>` : ''}</td>
            </tr>`).join('') || `<tr><td colspan="6" class="muted" style="padding:16px">${esc(t('mutants.none'))}</td></tr>`}
        </tbody>
      </table>
    </div>`;
}

/* ------------------------------------------------------------------ 质量页 */

function viewQuality() {
  if (!state.project) return emptyState();
  const q = state.quality || (state.results && state.results.quality) || null;
  const running = state.jobKind === 'quality';

  return `
    <div class="stack">
      <div class="row" style="align-items:flex-end">
        <div>
          <div class="section-title">${esc(t('quality.title'))}</div>
          <div class="section-desc">${esc(t('quality.sub'))}</div>
        </div>
        <div class="spacer"></div>
        <button class="btn primary" data-act="start-quality" ${state.runnerBusy ? 'disabled' : ''}>
          ${svgIcon('play')}${esc(t('quality.run'))}</button>
      </div>

      ${running || (state.job && state.job.kind === 'quality') ? `
      <div class="card">
        <div class="card-head"><div class="card-title">${esc(t('console.title'))}</div>${jobChip()}</div>
        <div class="card-body">${progressBar()}<div class="console" id="console" style="margin-top:12px"></div></div>
      </div>` : ''}

      ${!q ? `
        <div class="empty">${svgIcon('info')}
          <div class="title">${esc(t('quality.empty'))}</div>
          <div class="desc">${esc(t('quality.emptyDesc'))}</div>
        </div>` : qualityBody(q)}
    </div>`;
}

function qualityBody(q) {
  const flaky = q.flaky_tests || [];
  const weak = q.weak_assertions || [];
  const dups = q.duplicate_tests || [];
  const high = q.high_coverage_low_mutation || [];
  const axes = q.axes;
  const finds = flaky.length + weak.length + dups.length + high.length;

  return `
    <div class="kpis" style="grid-template-columns:repeat(4,minmax(0,1fr))">
      ${[['quality.flakyTests', flaky.length, 'warn'], ['quality.weak', weak.length, 'bad'],
         ['quality.dup', dups.length, ''], ['quality.highcov', high.length, 'info']].map(([k, n, cls]) => `
        <div class="kpi"><div class="kpi-label">${esc(t(k))}</div>
          <div class="kpi-value" style="color:${n ? `var(--${cls || 'text'})` : 'var(--text)'}">${n}</div>
          <div class="kpi-foot">${n ? '' : esc(t('quality.noFindings'))}</div></div>`).join('')}
    </div>

    ${axes ? axesCard(axes) : ''}

    ${q.suggestions && q.suggestions.length ? `
    <div class="card">
      <div class="card-head"><div class="card-title">${esc(t('quality.suggestions'))}</div></div>
      <div class="card-body stack" style="gap:8px">
        ${q.suggestions.map(s => `<div class="suggest">${svgIcon('bulb')}<div>${esc(s)}</div></div>`).join('')}
      </div>
    </div>` : ''}

    ${flaky.length ? `
    <div class="card">
      <div class="card-head"><div class="card-title">${esc(t('quality.flakyTests'))}</div>
        <span class="chip warn">${flaky.length}</span></div>
      <div class="card-body tight">${simpleTable(
        [t('quality.flakyTests'), 'runs', 'pass/fail', 'mode'],
        flaky.map(f => [`<span class="mono">${esc(f.test_id)}</span>`, f.runs, `${f.passed}/${f.failed}`,
          `<span class="chip warn">${esc(f.mode)}</span>`]))}</div>
    </div>` : ''}

    ${weak.length ? `
    <div class="card">
      <div class="card-head"><div class="card-title">${esc(t('quality.weak'))}</div>
        <span class="chip bad">${weak.length}</span></div>
      <div class="card-body tight">${simpleTable(
        [t('files.file'), 'test', 'reason'],
        weak.map(w => [`<span class="mono">${esc(w.file)}:${w.line}</span>`, esc(w.test),
          `<span class="chip bad">${esc(w.reason)}</span>`]))}</div>
    </div>` : ''}

    ${dups.length ? `
    <div class="card">
      <div class="card-head"><div class="card-title">${esc(t('quality.dup'))}</div>
        <span class="chip">${dups.length}</span></div>
      <div class="card-body tight">${simpleTable(['A', 'B'],
        dups.map(d => [`<span class="mono">${esc(d[0])}::${esc(d[1])}</span>`,
          `<span class="mono">${esc(d[2])}::${esc(d[3])}</span>`]))}</div>
    </div>` : ''}

    ${!finds ? `<div class="banner ok">${svgIcon('check')}<div>${esc(t('quality.noFindings'))}</div></div>` : ''}
  `;
}

function axesCard(axes) {
  const adequacy = typeof axes.adequacy === 'number' ? axes.adequacy * 100 : null;
  const redundancy = axes.redundancy || 0;
  const maint = axes.maintainability || 0;
  const notes = axes.notes || [];
  return `
    <div class="card">
      <div class="card-head"><div class="card-title">${esc(t('quality.axes'))}</div>
        <span class="small muted">sixth_sense 式：充分性 / 冗余 / 可维护性</span></div>
      <div class="card-body stack" style="gap:14px">
        <div class="axis">
          <span class="muted">${esc(t('axis.adequacy'))}</span>
          <div class="bar"><div style="width:${(adequacy || 0).toFixed(0)}%;
            background:${adequacy === null ? 'var(--line-strong)' : scoreColor(adequacy / 100)}"></div></div>
          <span class="val">${adequacy === null ? '—' : adequacy.toFixed(0)}</span>
        </div>
        <div class="row-gap" style="gap:40px">
          <div>
            <div class="kpi-label">${esc(t('axis.redundancy'))}</div>
            <div style="font-size:19px;font-weight:640;margin-top:3px">${redundancy}
              <small class="muted" style="font-size:11px;font-weight:400">${esc(t('axis.groups'))}</small></div>
          </div>
          <div>
            <div class="kpi-label">${esc(t('axis.maintainability'))}</div>
            <div style="font-size:19px;font-weight:640;margin-top:3px">${maint}
              <small class="muted" style="font-size:11px;font-weight:400">${esc(t('axis.weak'))}</small></div>
          </div>
        </div>
        ${notes.length ? `<div class="small muted">${notes.map(n => esc(n)).join('<br>')}</div>` : ''}
      </div>
    </div>`;
}

function simpleTable(headers, rows) {
  return `<div class="table-wrap"><table class="table">
    <thead><tr>${headers.map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead>
    <tbody>${rows.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join('')}</tr>`).join('')}</tbody>
  </table></div>`;
}

/* ------------------------------------------------------------------ 自检页 */

function viewSelftest() {
  const res = state.selftest;
  const cases = state.selftestCases || [];
  const running = state.jobKind === 'selftest';
  const summary = res ? res.summary : null;

  return `
    <div class="stack">
      <div class="row" style="align-items:flex-end">
        <div>
          <div class="section-title">${esc(t('selftest.title'))}</div>
          <div class="section-desc">${esc(t('selftest.sub'))}</div>
        </div>
        <div class="spacer"></div>
        <button class="btn primary" data-act="start-selftest" ${state.runnerBusy ? 'disabled' : ''}>
          ${svgIcon('play')}${esc(res ? t('selftest.rerun') : t('selftest.run'))}</button>
      </div>

      ${summary ? `
      <div class="kpis" style="grid-template-columns:repeat(4,minmax(0,1fr))">
        <div class="kpi"><div class="kpi-label">${esc(t('selftest.rate'))}</div>
          <div class="kpi-value" style="color:${summary.failed ? 'var(--bad)' : 'var(--ok)'}">
            ${((summary.passed / Math.max(1, summary.passed + summary.failed)) * 100).toFixed(0)}<small>%</small></div>
          <div class="kpi-foot">${summary.passed}/${summary.passed + summary.failed}</div></div>
        <div class="kpi"><div class="kpi-label">${esc(t('selftest.pass'))}</div>
          <div class="kpi-value" style="color:var(--ok)">${summary.passed}</div></div>
        <div class="kpi"><div class="kpi-label">${esc(t('selftest.fail'))}</div>
          <div class="kpi-value" style="color:${summary.failed ? 'var(--bad)' : 'var(--text)'}">${summary.failed}</div></div>
        <div class="kpi"><div class="kpi-label">${esc(t('selftest.skip'))}</div>
          <div class="kpi-value">${summary.skipped}</div></div>
      </div>
      ${summary.failed ? `<div class="banner bad">${svgIcon('alert')}<div>${esc(t('selftest.untrusted'))}</div></div>` : ''}
      ` : ''}

      <div class="grid cols-2">
        <div class="card">
          <div class="card-head"><div class="card-title">${esc(t('selftest.cases'))}</div>
            <span class="chip outline">${cases.length}</span></div>
          <div class="card-body tight">
            <div class="table-wrap">
              <table class="table">
                <thead><tr><th>${esc(t('selftest.case'))}</th><th>${esc(t('selftest.kind'))}</th>
                  <th class="right">${esc(t('selftest.verdict'))}</th></tr></thead>
                <tbody>${cases.map(c => {
                  const r = res && (res.results || []).find(x => x.case_id === c.case_id);
                  const chip = !r ? `<span class="chip outline">—</span>`
                    : r.skipped ? `<span class="chip">${esc(t('selftest.skip'))}</span>`
                    : r.pass ? `<span class="chip ok">${esc(t('selftest.pass'))}</span>`
                    : `<span class="chip bad">${esc(t('selftest.fail'))}</span>`;
                  return `<tr><td class="mono">${esc(c.case_id)}</td>
                    <td class="small muted">${esc(c.kind)}</td>
                    <td class="right">${chip}</td></tr>`;
                }).join('')}</tbody>
              </table>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-head"><div class="card-title">${esc(t('console.title'))}</div>${jobChip()}</div>
          <div class="card-body">${progressBar()}<div class="console" id="console" style="margin-top:12px"></div></div>
        </div>
      </div>

      ${res && res.results && res.results.length ? `
      <div class="card">
        <div class="card-head"><div class="card-title">${esc(t('selftest.verdict'))}</div></div>
        <div class="card-body tight">
          <div class="table-wrap">
            <table class="table">
              <thead><tr><th>${esc(t('selftest.case'))}</th><th>${esc(t('selftest.expected'))}</th>
                <th>${esc(t('selftest.actual'))}</th><th>${esc(t('selftest.verdict'))}</th>
                <th class="right">${esc(t('kpi.duration'))}</th><th>${esc(t('mutants.message'))}</th></tr></thead>
              <tbody>${res.results.map(r => `
                <tr><td class="mono">${esc(r.case_id)}</td><td class="code">${esc(r.expected)}</td>
                  <td class="code">${esc(r.actual)}</td>
                  <td>${r.skipped ? `<span class="chip">${esc(t('selftest.skip'))}</span>`
                    : r.pass ? `<span class="chip ok">PASS</span>` : `<span class="chip bad">FAIL</span>`}</td>
                  <td class="num">${Number(r.duration_sec || 0).toFixed(1)}s</td>
                  <td class="trunc small muted" title="${esc(r.message || '')}">${esc(r.message || '')}</td></tr>`).join('')}
              </tbody>
            </table>
          </div>
        </div>
      </div>` : `
        <div class="empty">${svgIcon('check')}
          <div class="title">${esc(t('selftest.empty'))}</div>
          <div class="desc">${esc(t('selftest.emptyDesc'))}</div>
        </div>`}
    </div>`;
}

/* ------------------------------------------------------------------ 项目页 */

function viewProject() {
  if (!state.project) return emptyState();
  const p = state.project;
  const cfg = p.config;
  const recent = ((state.meta && state.meta.recent) || []).filter(x => x !== p.path);

  return `
    <div class="stack">
      <div>
        <div class="section-title">${esc(p.name)}</div>
        <div class="section-desc mono">${esc(p.path)}</div>
      </div>
      ${configIssueBanner()}

      <div class="grid cols-2">
        <div class="card">
          <div class="card-head"><div class="card-title">${esc(t('project.info'))}</div>
            <button class="btn small" data-act="refresh">${svgIcon('refresh')}${esc(t('action.refresh'))}</button></div>
          <div class="card-body">
            <dl class="kv">
              <dt>${esc(t('project.language'))}</dt><dd>${esc(p.language)}</dd>
              <dt>${esc(t('project.testCmd'))}</dt><dd>${esc(cfg ? cfg.test_cmd : '—')}</dd>
              <dt>${esc(t('project.buildCmd'))}</dt><dd>${esc(cfg && cfg.build_cmd ? cfg.build_cmd : '—')}</dd>
              <dt>${esc(t('project.selection'))}</dt>
              <dd>${esc(cfg ? cfg.source_roots.join(', ') : '—')} / ${esc(cfg ? cfg.test_roots.join(', ') : '—')}</dd>
              <dt>${esc(t('project.trust'))}</dt>
              <dd>${p.trusted ? `<span class="chip ok">${esc(t('project.trusted'))}</span>`
                : `<span class="chip warn">${esc(t('project.untrusted'))}</span>`}
                ${cfg ? `<span class="small muted"> fingerprint ${esc(cfg.fingerprint)}</span>` : ''}</dd>
            </dl>
            <div class="row-gap" style="margin-top:14px">
              ${p.trusted
                ? `<button class="btn small danger" data-act="revoke-trust">${esc(t('project.revoke'))}</button>`
                : `<button class="btn small primary" data-act="trust-only" ${p.has_config ? '' : 'disabled'}>${esc(t('project.trustAction'))}</button>`}
              ${!p.has_config ? `<button class="btn small" data-act="init-config">${esc(t('project.init'))}</button>` : ''}
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-head"><div class="card-title">${esc(t('project.reports'))}</div>
            ${reportLinks()}</div>
          <div class="card-body">
            ${p.last_report ? `
              <dl class="kv">
                <dt>generated</dt><dd>${esc(p.last_report.generated_at || fmtTime(p.last_report.mtime))}</dd>
                <dt>${esc(t('kpi.score'))}</dt><dd>${fmtPct(p.last_report.score)}</dd>
                <dt>${esc(t('kpi.mutants'))}</dt><dd>${p.last_report.total}</dd>
                <dt>${esc(t('kpi.duration'))}</dt><dd>${fmtDur(p.last_report.duration_sec)}</dd>
              </dl>` : `<div class="muted small">${esc(t('project.noReports'))}</div>`}
            <div class="stack" style="margin-top:14px;gap:8px">
              ${recent.map(r => `
                <div class="row-gap" style="justify-content:space-between">
                  <span class="mono small muted" title="${esc(r)}">${esc(shortPath(r, 48))}</span>
                  <button class="btn small" data-recent="${esc(r)}">${esc(t('action.openProject'))}</button>
                </div>`).join('')}
            </div>
          </div>
        </div>
      </div>

      ${p.language === 'python' ? interpreterCard() : ''}

      ${cfg ? `
      <div class="card">
        <div class="card-head">
          <div><div class="card-title">${esc(t('project.config'))}</div>
            <div class="card-sub">${esc(t('project.saveWarn'))}</div></div>
          <button class="btn primary small" data-act="save-config">${esc(t('project.save'))}</button>
        </div>
        <div class="card-body">
          <textarea class="input" id="configText" spellcheck="false">${esc(p.config_text || '')}</textarea>
        </div>
      </div>` : ''}
    </div>`;
}

/* ------------------------------------------------------------------ 运行状态组件 */

function interpreterCard() {
  const data = state.interpreters;
  const rows = (data && data.candidates) || [];
  return `
    <div class="card">
      <div class="card-head">
        <div><div class="card-title">${esc(t('interp.title'))}</div>
          <div class="card-sub">${esc(t('interp.desc'))}</div></div>
        <span class="chip ${data && data.assigned ? 'ok' : 'outline'}">
          ${data && data.assigned ? esc(t('interp.current')) : esc(t('interp.autoMode'))}</span>
      </div>
      <div class="card-body tight">
        ${rows.length ? rows.map(row => `
          <div class="row-gap" style="padding:9px 16px;border-bottom:1px solid var(--line);gap:10px">
            <span class="chip ${row.pytest ? 'ok' : 'bad'}">${esc(row.pytest ? t('interp.pytestOk') : t('interp.pytestMissing'))}</span>
            <span class="mono small" style="word-break:break-all;flex:1">${esc(row.path)}</span>
            ${row.self ? `<span class="chip outline">${esc(t('interp.self'))}</span>` : ''}
            ${row.assigned ? `<span class="chip ok">${esc(t('interp.current'))}</span>`
              : `<button class="btn small" data-interp="${esc(row.path)}">${esc(t('interp.use'))}</button>`}
          </div>`).join('')
          : `<div class="muted small" style="padding:14px 16px">—</div>`}
        <div class="row-gap" style="padding:10px 16px;justify-content:flex-end">
          ${data && data.assigned ? `<button class="btn small" data-act="interp-auto">${esc(t('interp.auto'))}</button>` : ''}
        </div>
      </div>
    </div>`;
}

function jobChip() {
  const inner = jobChipInner();
  return `<span id="jobChipHost">${inner}</span>`;
}

function jobChipInner() {
  if (!state.job) return `<span class="chip outline">idle</span>`;
  const j = state.job;
  const map = {
    queued: ['', 'queued'], running: ['info', 'running'], done: ['ok', 'done'],
    failed: ['bad', 'failed'], cancelled: ['', 'cancelled'],
  };
  const [cls, label] = map[j.status] || ['', j.status];
  return `<span class="chip ${cls}">${j.status === 'running' ? `<span class="dot pulse"></span>` : '<span class="dot"></span>'}${esc(label)}
    ${j.exit_code != null ? ` · exit ${j.exit_code}` : ''}</span>`;
}

function progressBar() {
  if (!state.job) return '';
  const p = state.job.progress || {};
  const total = p.total || 0;
  const done = p.done || 0;
  const pct = total ? Math.min(100, done / total * 100) : (state.job.status === 'done' ? 100 : 0);
  return `<div id="progressBlock">
    <div class="progress"><div style="width:${pct.toFixed(1)}%"></div></div>
    <div class="progress-meta"><span>${esc(t('run.progress'))}</span>
      <span>${total ? `${done} / ${total}` : esc(state.job.status)}${total ? ` · ${pct.toFixed(0)}%` : ''}</span></div>
  </div>`;
}

function restoreConsole() {
  const box = $('#console');
  if (!box) return;
  if (!state.logs.length) {
    box.innerHTML = `<div class="ln muted">${esc(t('console.empty'))}</div>`;
    return;
  }
  box.innerHTML = state.logs.map(l => logLine(l)).join('');
  box.scrollTop = box.scrollHeight;
}

function logLine(l) {
  const d = new Date((l.t || 0) * 1000);
  const ts = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`;
  return `<div class="ln ${l.lvl}"><span class="ts">${ts}</span>${esc(localizeText(l.text))}</div>`;
}

function appendLogs(entries) {
  state.logs.push(...entries);
  if (state.logs.length > 3000) state.logs = state.logs.slice(-3000);
  const box = $('#console');
  if (!box) return;
  if (box.querySelector('.muted') && !state.logs.length) box.innerHTML = '';
  const nearBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 60;
  const frag = document.createElement('div');
  frag.innerHTML = entries.map(l => logLine(l)).join('');
  while (frag.firstChild) box.appendChild(frag.firstChild);
  if (nearBottom) box.scrollTop = box.scrollHeight;
}

/* ------------------------------------------------------------------ 任务 */

function collectOptions() {
  const val = id => { const e = document.getElementById(id); return e ? e.value.trim() : ''; };
  const chk = id => { const e = document.getElementById(id); return !!(e && e.checked); };
  return {
    parallel: val('optParallel'),
    timeout: val('optTimeout'),
    operators: val('optOperators'),
    incremental: chk('optIncremental'),
    diffRef: val('optDiffRef'),
    testSelection: chk('optTestSelection'),
    flaky: chk('optFlaky'),
    noQuality: chk('optNoQuality'),
    noCache: chk('optNoCache'),
  };
}

async function startRun(forceTrust = false) {
  if (!state.project) return toast(t('toast.noProject'), 'error');
  const options = { ...collectOptions(), allow_commands: forceTrust || !!(state.project && state.project.trusted) };
  state.runOptions = options;
  try {
    const job = await api('/api/run', { method: 'POST', body: { path: state.project.path, options } });
    beginJob(job, 'run');
    toast(t('run.queued'));
  } catch (e) {
    toast(t('toast.error') + ': ' + e.message, 'error');
  }
}

async function startSelftest() {
  try {
    const job = await api('/api/selftest', { method: 'POST', body: {} });
    beginJob(job, 'selftest');
  } catch (e) {
    toast(t('toast.error') + ': ' + e.message, 'error');
  }
}

async function startQuality() {
  if (!state.project) return toast(t('toast.noProject'), 'error');
  if (!state.project.trusted) return toast(t('run.trustTitle'), 'error');
  try {
    const job = await api('/api/quality', { method: 'POST', body: { path: state.project.path, flaky: false } });
    beginJob(job, 'quality');
  } catch (e) {
    toast(t('toast.error') + ': ' + e.message, 'error');
  }
}

function beginJob(job, kind) {
  state.job = job;
  state.jobKind = kind;
  state.logs = [];
  state.logIndex = 0;
  state.runnerBusy = true;
  state.view = kind === 'selftest' ? 'selftest' : (kind === 'quality' ? 'quality' : 'run');
  render();
  watchJob(job.id, kind);
}

function watchJob(jobId, kind) {
  if (state.eventSource) { try { state.eventSource.close(); } catch { } }
  state.logIndex = 0;
  const es = new EventSource(`/api/jobs/${jobId}/events?since=0`);
  state.eventSource = es;

  es.addEventListener('state', ev => {
    const snap = JSON.parse(ev.data);
    const prevStatus = state.job ? state.job.status : null;
    state.job = { ...snap };
    const progressHost = document.getElementById('progressBlock');
    if (progressHost) progressHost.outerHTML = progressBar();
    const chipHost = document.getElementById('jobChipHost');
    if (chipHost) chipHost.outerHTML = jobChip();
    if (prevStatus !== snap.status && snap.status === 'running') render();
  });
  es.addEventListener('log', ev => {
    const entries = JSON.parse(ev.data);
    if (!entries.length) return;
    const last = entries[entries.length - 1];
    if (last.i < state.logIndex) return;
    state.logIndex = last.i + 1;
    appendLogs(entries);
    state.job.log_count = (state.job.log_count || 0) + entries.length;
  });
  es.addEventListener('end', async ev => {
    const snap = JSON.parse(ev.data);
    es.close();
    state.eventSource = null;
    state.job = snap;
    state.runnerBusy = false;
    await finishJob(snap, kind);
  });
  es.onerror = () => {
    // 服务端已关闭流或网络抖动：用轮询兜底，避免界面卡在 running
    if (!state.job || state.job.status === 'done' || state.job.status === 'failed') return;
    setTimeout(async () => {
      try {
        const snap = await api(`/api/jobs/${jobId}?since=${state.logIndex}`);
        state.job = snap;
        if (snap.logs && snap.logs.length) {
          appendLogs(snap.logs);
          state.logIndex = snap.logs[snap.logs.length - 1].i + 1;
        }
        if (snap.status === 'done' || snap.status === 'failed') {
          state.runnerBusy = false;
          await finishJob(snap, kind);
        } else {
          render();
        }
      } catch { /* 忽略 */ }
    }, 1200);
  };
}

async function finishJob(snap, kind) {
  const rc = snap.exit_code;
  if (kind === 'run') {
    const result = snap.result || null;
    if (result && result.results) {
      state.results = result.results;
      state.quality = result.results.quality || null;
      toast(`${t('toast.runDone')} · ${fmtPct(result.results.summary.mutation_score_percent)}`,
        rc === 0 ? 'ok' : '');
    } else if (rc === 2) {
      toast(t('toast.runFailed') + ' (exit 2)', 'error');
    } else if (rc === 1) {
      toast(t('toast.runFailed') + ' · gate', '');
    }
    if (state.project) state.project = await loadProjectInfo(state.project.path, false).catch(() => state.project);
    render();
    return;
  }
  if (kind === 'selftest') {
    state.selftest = snap.result || null;
    toast(t('toast.selftestDone'), rc === 0 ? 'ok' : 'error');
    render();
    return;
  }
  if (kind === 'quality') {
    state.quality = snap.result || null;
    toast(t('toast.qualityDone'), 'ok');
    render();
  }
}

/* ------------------------------------------------------------------ 项目加载 */

async function loadInterpreters(path) {
  if (state.interpLoading) return;
  if (state.interpreters && state.interpreters.path === path) return;
  if (state.interpFailed === path) return;
  state.interpLoading = true;
  try {
    state.interpreters = await api('/api/interpreters?path=' + encodeURIComponent(path));
    state.interpFailed = null;
  } catch {
    state.interpreters = null;
    state.interpFailed = path;
  } finally {
    state.interpLoading = false;
    if (state.view === 'project') render();
  }
}

async function loadProjectInfo(path, setView = true) {
  const info = await api('/api/project/open', { method: 'POST', body: { path } });
  state.project = info;
  if (setView) state.view = 'overview';
  // 加载完整结果（用于表格），失败不影响主流程
  try {
    if (info.has_config) {
      const doc = await api(`/api/report?path=${encodeURIComponent(info.path)}&file=results.json`);
      state.results = doc && doc.schema ? doc : null;
      state.quality = (doc && doc.quality) || null;
    } else {
      state.results = null;
      state.quality = null;
    }
  } catch {
    state.results = null;
  }
  render();
  return info;
}

async function openProjectDialog() {
  const start = (state.project && state.project.path) || (state.meta && state.meta.last_project) || '';
  await browseTo(start);
  $('#modal').hidden = false;
}

async function browseTo(path) {
  try {
    const data = await api('/api/browse' + (path ? '?path=' + encodeURIComponent(path) : ''));
    state.browsing = data;
    renderBrowser();
  } catch (e) {
    toast(e.message, 'error');
  }
}

function renderBrowser() {
  const b = state.browsing;
  $('#modalPath').textContent = b.path || '';
  const roots = (b.roots || []).map(r => `
    <div class="dir" data-browse="${esc(r)}">${svgIcon('folder')}<span class="mono">${esc(r)}</span></div>`).join('');
  const dirs = (b.dirs || []).map(d => `
    <div class="dir" data-browse="${esc(d.path)}">
      ${svgIcon('folder')}
      <span>${esc(d.name)}</span>
      ${d.has_config ? `<span class="chip ok">config</span>` : ''}
      ${d.hints && d.hints.length ? `<span class="chip outline">${esc(d.hints.join(' / '))}</span>` : ''}
      <span class="pathhint">›</span>
    </div>`).join('');
  $('#browser').innerHTML = roots + (dirs || `<div class="empty-line">${esc(t('modal.noDirs'))}</div>`);
  $('#modalUp').disabled = !b.parent;
}

/* ------------------------------------------------------------------ 事件绑定 */

function bindView() {
  const view = $('#view');

  view.querySelectorAll('[data-act]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const act = btn.dataset.act;
      if (act === 'open-project') return openProjectDialog();
      if (act === 'goto-run') { state.view = 'run'; return render(); }
      if (act === 'goto-selftest') { state.view = 'selftest'; return render(); }
      if (act === 'goto-project') { state.view = 'project'; return render(); }
      if (act === 'start-run') return startRun(false);
      if (act === 'trust-run') {
        try {
          await api('/api/project/trust', { method: 'POST', body: { path: state.project.path } });
          state.project = await loadProjectInfo(state.project.path, false);
          toast(t('toast.trusted'), 'ok');
          state.view = 'run';
          return startRun(true);
        } catch (e) { return toast(e.message, 'error'); }
      }
      if (act === 'trust-only') {
        try {
          state.project = await api('/api/project/trust', { method: 'POST', body: { path: state.project.path } });
          toast(t('toast.trusted'), 'ok');
          render();
        } catch (e) { toast(e.message, 'error'); }
        return;
      }
      if (act === 'revoke-trust') {
        try {
          state.project = await api('/api/project/revoke', { method: 'POST', body: { path: state.project.path } });
          toast(t('toast.revoked'));
          render();
        } catch (e) { toast(e.message, 'error'); }
        return;
      }
      if (act === 'init-config') {
        try {
          const info = await api('/api/project/init', { method: 'POST', body: { path: state.project.path } });
          state.project = info;
          toast(t('project.saved'), 'ok');
          render();
        } catch (e) { toast(e.message, 'error'); }
        return;
      }
      if (act === 'save-config') {
        const text = $('#configText') ? $('#configText').value : '';
        try {
          state.project = await api('/api/project/config', { method: 'POST', body: { path: state.project.path, text } });
          toast(t('project.saved') + ' · ' + t('project.saveWarn'), 'ok');
          render();
        } catch (e) { toast(e.message, 'error'); }
        return;
      }
      if (act === 'interp-auto') {
        try {
          state.interpreters = await api('/api/interpreters', {
            method: 'POST', body: { path: state.project.path, executable: null },
          });
          toast(t('interp.auto'), 'ok');
          render();
        } catch (e) { toast(e.message, 'error'); }
        return;
      }
      if (act === 'start-selftest') return startSelftest();
      if (act === 'start-quality') return startQuality();
      if (act === 'refresh') {
        if (state.project) { await loadProjectInfo(state.project.path, false); toast(t('action.refresh')); }
        return;
      }
    });
  });

  view.querySelectorAll('[data-interp]').forEach(btn => {
    btn.addEventListener('click', async () => {
      try {
        state.interpreters = await api('/api/interpreters', {
          method: 'POST', body: { path: state.project.path, executable: btn.dataset.interp },
        });
        toast(t('interp.change'), 'ok');
        render();
      } catch (e) { toast(e.message, 'error'); }
    });
  });

  view.querySelectorAll('[data-filter]').forEach(btn => {
    btn.addEventListener('click', () => {
      state.mutantFilter = btn.dataset.filter;
      render();
    });
  });

  const search = $('#mutantSearch');
  if (search) {
    let timer = null;
    search.addEventListener('input', () => {
      state.mutantSearch = search.value;
      clearTimeout(timer);
      timer = setTimeout(() => {
        const pos = search.selectionStart;
        render();
        const next = $('#mutantSearch');
        if (next) { next.focus(); next.setSelectionRange(pos, pos); }
      }, 260);
    });
  }

  view.querySelectorAll('[data-recent]').forEach(node => {
    node.addEventListener('click', async () => {
      try { await loadProjectInfo(node.dataset.recent); toast(t('toast.projectOpened'), 'ok'); }
      catch (e) { toast(e.message, 'error'); }
    });
  });

  // 保留用户输入（重渲染后回填）
  if (state.runOptions) {
    const map = {
      optParallel: 'parallel', optTimeout: 'timeout', optOperators: 'operators', optDiffRef: 'diffRef',
    };
    for (const [id, key] of Object.entries(map)) {
      const e = document.getElementById(id);
      if (e && state.runOptions[key] != null && state.runOptions[key] !== '') e.value = state.runOptions[key];
    }
  }
}

function bindGlobal() {
  $$('#nav .nav-item').forEach(btn => {
    btn.addEventListener('click', () => { state.view = btn.dataset.view; render(); });
  });

  $('#btnOpenProject').addEventListener('click', openProjectDialog);
  $('#btnQuickRun').addEventListener('click', () => {
    if (!state.project) { state.view = 'overview'; render(); return openProjectDialog(); }
    state.view = 'run'; render();
    if (state.project.trusted) startRun(false);
  });

  $('#langSwitch').querySelectorAll('button').forEach(btn => {
    btn.addEventListener('click', () => {
      state.lang = btn.dataset.lang;
      localStorage.setItem('mt.lang', state.lang);
      render();
    });
  });

  $('#themeToggle').addEventListener('click', () => {
    state.theme = state.theme === 'light' ? 'dark' : 'light';
    localStorage.setItem('mt.theme', state.theme);
    render();
  });

  // 目录浏览弹窗
  $('#modalClose').addEventListener('click', () => { $('#modal').hidden = true; });
  $('#modal').addEventListener('click', e => { if (e.target.id === 'modal') $('#modal').hidden = true; });
  $('#browser').addEventListener('click', e => {
    const row = e.target.closest('[data-browse]');
    if (row) browseTo(row.dataset.browse);
  });
  $('#modalUp').addEventListener('click', () => { if (state.browsing.parent) browseTo(state.browsing.parent); });
  $('#modalUse').addEventListener('click', async () => {
    const path = state.browsing.path;
    if (!path) return;
    $('#modal').hidden = true;
    try {
      await loadProjectInfo(path);
      toast(t('toast.projectOpened'), 'ok');
    } catch (e) { toast(e.message, 'error'); }
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !$('#modal').hidden) $('#modal').hidden = true;
  });
}

/* ------------------------------------------------------------------ 启动 */

async function boot() {
  render();
  bindGlobal();
  try {
    state.meta = await api('/api/meta');
    state.selftestCases = (await api('/api/selftest/cases')).cases || [];
    const lastSelf = await api('/api/selftest/last').catch(() => null);
    if (lastSelf && lastSelf.result) state.selftest = lastSelf.result;
  } catch (e) {
    toast('无法连接本地服务: ' + e.message, 'error');
    return;
  }
  const url = new URL(location.href);
  const qLang = url.searchParams.get('lang');
  if (qLang === 'zh' || qLang === 'en') state.lang = qLang;
  const qTheme = url.searchParams.get('theme');
  if (qTheme === 'light' || qTheme === 'dark') state.theme = qTheme;
  render();
  const wanted = url.searchParams.get('project') || state.meta.last_project;
  const wantedView = url.searchParams.get('view');
  if (wanted) {
    try { await loadProjectInfo(wanted); }
    catch { render(); }
  }
  if (wantedView && ['overview', 'run', 'quality', 'selftest', 'project'].includes(wantedView)) {
    state.view = wantedView;
    render();
  } else if (!wanted) {
    render();
  }
}

boot();
