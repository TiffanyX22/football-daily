/** Independent cloud timer. Keep the token ONLY in private Script Properties. */
const FOOTBALL_REPO = 'TiffanyX22/football-daily';
const FOOTBALL_ZONE = 'America/Los_Angeles';

function dueDay(now) {
  const local = Utilities.formatDate(now, FOOTBALL_ZONE, 'yyyy-MM-dd');
  const hour = Number(Utilities.formatDate(now, FOOTBALL_ZONE, 'H'));
  if (hour >= 16) return local;
  const parts = local.split('-').map(Number);
  return new Date(Date.UTC(parts[0], parts[1] - 1, parts[2] - 1)).toISOString().slice(0, 10);
}

function github(path, payload) {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('Configure a repository-only GitHub token in private Script Properties.');
  const options = {method: payload ? 'post' : 'get', muteHttpExceptions: true,
    headers: {Authorization: 'Bearer ' + token, Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}};
  if (payload) { options.contentType = 'application/json'; options.payload = JSON.stringify(payload); }
  const response = UrlFetchApp.fetch('https://api.github.com/repos/' + FOOTBALL_REPO + path, options);
  const status = response.getResponseCode();
  if (status < 200 || status >= 300) throw new Error('GitHub API HTTP ' + status + ' for ' + path.split('?')[0]);
  return response.getContentText() ? JSON.parse(response.getContentText()) : null;
}

function stateFile(name) {
  const file = github('/contents/data/' + name);
  return JSON.parse(Utilities.newBlob(Utilities.base64Decode(file.content)).getDataAsString());
}

function dispatch(workflow, inputs, now) {
  const props = PropertiesService.getScriptProperties();
  const key = 'dispatch_' + workflow;
  if (now.getTime() - Number(props.getProperty(key) || 0) < 10 * 60000) return false;
  const runs = github('/actions/workflows/' + workflow + '/runs?per_page=10').workflow_runs;
  if (runs.some(run => ['queued', 'in_progress', 'pending', 'waiting', 'requested'].includes(run.status))) return false;
  github('/actions/workflows/' + workflow + '/dispatches', {ref: 'main', inputs: inputs || {}});
  props.setProperty(key, String(now.getTime()));
  return true;
}

function lateNotice(day, entry, now) {
  const local = Utilities.formatDate(now, FOOTBALL_ZONE, 'yyyy-MM-dd HH:mm');
  if (day !== local.slice(0, 10) || local.slice(11) < '16:20' || Number(entry.accepted || 0) > 0) return;
  const props = PropertiesService.getScriptProperties();
  if (props.getProperty('late_notice') === day) return;
  const recipient = props.getProperty('REPORT_EMAIL') || Session.getEffectiveUser().getEmail();
  if (!recipient) throw new Error('Configure REPORT_EMAIL in Script Properties for late-delivery alerts.');
  MailApp.sendEmail(recipient, '足球日报延迟提醒 ' + day,
    '截至洛杉矶时间 ' + local + '，尚未确认今天日报邮件已发送。独立定时器已尝试补跑。\n查看运行：https://github.com/' + FOOTBALL_REPO + '/actions\n请勿把本提醒当作报告已生成。');
  props.setProperty('late_notice', day);
}

function resolveNameRequests(now) {
  const requests = stateFile('player-name-requests.json');
  const names = {};
  Object.values(requests).forEach(r => Object.entries(r.players).forEach(([id, english]) => names[id] = english));
  if (!Object.keys(names).length) return false;
  const props = PropertiesService.getScriptProperties();
  if (now.getTime() - Number(props.getProperty('name_attempt') || 0) < 600000) return true;
  props.setProperty('name_attempt', String(now.getTime()));
  const translations = [];
  Object.entries(names).slice(0, 100).forEach(([id, english]) => {
    const chinese = LanguageApp.translate(english, 'en', 'zh-CN').trim();
    if (/[\u4e00-\u9fff]/.test(chinese)) translations.push({id, english, chinese});
  });
  if (translations.length) dispatch('player-names.yml', {translations: JSON.stringify(translations)}, now);
  console.log('Chinese name requests: ' + Object.keys(names).length + '; transliterations ready: ' + translations.length);
  return true;
}

function footballTick() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  try {
    const now = new Date();
    const day = dueDay(now);
    const deliveries = stateFile('daily-delivery.json');
    const entry = deliveries[day] || {};
    lateNotice(day, entry, now);
    if (resolveNameRequests(now)) return;
    if (!entry.status || entry.status === 'waiting') dispatch('daily.yml', {report_date: day}, now);
    // Google egress may be blocked by ESPN. GitHub performs the lightweight
    // match check itself; the Google timer only uses the GitHub API.
    dispatch('real-madrid.yml', {}, now);
    console.log('Checked football delivery for ' + day + '; Madrid cloud check scheduled when due');
  } finally { lock.releaseLock(); }
}

function installFootballTimer() {
  // Check API permissions before installing, without printing any credentials.
  github('/actions/workflows/daily.yml');
  stateFile('daily-delivery.json');
  ScriptApp.getProjectTriggers().filter(trigger => trigger.getHandlerFunction() === 'footballTick')
    .forEach(trigger => ScriptApp.deleteTrigger(trigger));
  ScriptApp.newTrigger('footballTick').timeBased().everyMinutes(5).create();
  footballTick();
  console.log('Independent cloud timer installed. This is not a strict delivery SLA.');
}
