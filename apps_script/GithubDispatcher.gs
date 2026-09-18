/**
 * Greating Instagram Dashboard
 * GitHub Actions Dispatcher v0.7.0
 *
 * 역할:
 * - 08시대 / 19시대 동일한 GitHub Actions workflow_dispatch 호출
 * - Streamlit Overview의 수동 실행 요청을 Web App doPost로 수신
 * - Meta API 수집 자체는 하지 않음
 *
 * Script Properties 필수값:
 * GITHUB_OWNER
 * GITHUB_REPO
 * GITHUB_WORKFLOW
 * GITHUB_REF
 * GITHUB_TOKEN
 * WEBAPP_SECRET
 */

const DISPATCH_VERSION = '0.7.0';
const MORNING_HANDLER = 'runInstagramMorning';
const EVENING_HANDLER = 'runInstagramEvening';

function runInstagramMorning() {
  return dispatchGithubWorkflow_('apps_script_0800');
}

function runInstagramEvening() {
  return dispatchGithubWorkflow_('apps_script_1900');
}

/**
 * 처음 한 번만 직접 실행.
 * 기존 동일 함수 트리거를 삭제한 뒤 08시대 / 19시대 트리거를 재생성한다.
 * Apps Script 시간 트리거는 정확히 08:00:00 / 19:00:00을 보장하지 않는다.
 */
function setupInstagramTriggers() {
  const targets = new Set([MORNING_HANDLER, EVENING_HANDLER]);

  ScriptApp.getProjectTriggers().forEach((trigger) => {
    if (targets.has(trigger.getHandlerFunction())) {
      ScriptApp.deleteTrigger(trigger);
    }
  });

  ScriptApp.newTrigger(MORNING_HANDLER)
    .timeBased()
    .atHour(8)
    .nearMinute(0)
    .everyDays(1)
    .create();

  ScriptApp.newTrigger(EVENING_HANDLER)
    .timeBased()
    .atHour(19)
    .nearMinute(0)
    .everyDays(1)
    .create();

  const result = {
    ok: true,
    version: DISPATCH_VERSION,
    message: '08시대 / 19시대 GitHub Actions 호출 트리거 생성 완료',
  };

  console.log(JSON.stringify(result));
  return result;
}

/**
 * Apps Script Web App endpoint.
 * Streamlit의 "지금 수집" 버튼이 이 URL로 POST한다.
 *
 * 요청 JSON:
 * {
 *   "secret": "...",
 *   "source": "streamlit_overview"
 * }
 */
function doPost(e) {
  try {
    const body = parseJsonBody_(e);
    const props = PropertiesService.getScriptProperties();
    const expectedSecret = requireProperty_(props, 'WEBAPP_SECRET');
    const receivedSecret = String(body.secret || '');

    if (!receivedSecret || receivedSecret !== expectedSecret) {
      return jsonResponse_({
        ok: false,
        status: 401,
        message: 'Unauthorized',
      });
    }

    const source = String(body.source || 'streamlit_overview').slice(0, 100);
    const result = dispatchGithubWorkflow_(source);

    return jsonResponse_({
      ok: true,
      status: 202,
      message: 'GitHub Actions workflow dispatch accepted',
      dispatched_at: result.dispatched_at,
      source: source,
      version: DISPATCH_VERSION,
    });
  } catch (error) {
    console.error(error && error.stack ? error.stack : error);

    return jsonResponse_({
      ok: false,
      status: 500,
      message: String(error && error.message ? error.message : error),
      version: DISPATCH_VERSION,
    });
  }
}

/**
 * 배포 후 브라우저에서 endpoint 상태를 가볍게 확인할 때 사용.
 * 토큰/설정값은 노출하지 않는다.
 */
function doGet() {
  const props = PropertiesService.getScriptProperties();

  return jsonResponse_({
    ok: true,
    service: 'Greating Instagram GitHub Dispatcher',
    version: DISPATCH_VERSION,
    last_dispatch_at: props.getProperty('LAST_DISPATCH_AT') || '',
    last_dispatch_source: props.getProperty('LAST_DISPATCH_SOURCE') || '',
  });
}

function dispatchGithubWorkflow_(source) {
  const lock = LockService.getScriptLock();

  if (!lock.tryLock(10000)) {
    throw new Error('Another dispatch request is currently being processed.');
  }

  try {
    const props = PropertiesService.getScriptProperties();

    const owner = requireProperty_(props, 'GITHUB_OWNER');
    const repo = requireProperty_(props, 'GITHUB_REPO');
    const workflow = requireProperty_(props, 'GITHUB_WORKFLOW');
    const ref = props.getProperty('GITHUB_REF') || 'main';
    const token = requireProperty_(props, 'GITHUB_TOKEN');

    const url = [
      'https://api.github.com/repos',
      encodeURIComponent(owner),
      encodeURIComponent(repo),
      'actions/workflows',
      encodeURIComponent(workflow),
      'dispatches',
    ].join('/');

    const payload = {
      ref: ref,
      inputs: {
        source: String(source || 'apps_script').slice(0, 100),
      },
    };

    const response = UrlFetchApp.fetch(url, {
      method: 'post',
      contentType: 'application/json',
      headers: {
        Authorization: 'Bearer ' + token,
        Accept: 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'greating-instagram-dashboard-dispatcher',
      },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true,
    });

    const statusCode = response.getResponseCode();
    const responseText = response.getContentText();

    // GitHub workflow_dispatch success response = 204 No Content.
    if (statusCode !== 204) {
      throw new Error(
        'GitHub dispatch failed. HTTP ' +
        statusCode +
        (responseText ? ' | ' + responseText : '')
      );
    }

    const dispatchedAt = Utilities.formatDate(
      new Date(),
      Session.getScriptTimeZone(),
      'yyyy-MM-dd HH:mm:ss'
    );

    props.setProperties({
      LAST_DISPATCH_AT: dispatchedAt,
      LAST_DISPATCH_SOURCE: String(source || 'apps_script'),
    });

    const result = {
      ok: true,
      status: 204,
      dispatched_at: dispatchedAt,
      source: String(source || 'apps_script'),
      ref: ref,
      workflow: workflow,
    };

    console.log(JSON.stringify(result));
    return result;
  } finally {
    lock.releaseLock();
  }
}

function requireProperty_(props, key) {
  const value = props.getProperty(key);

  if (!value) {
    throw new Error('Missing Script Property: ' + key);
  }

  return value;
}

function parseJsonBody_(e) {
  if (!e || !e.postData || !e.postData.contents) {
    return {};
  }

  try {
    return JSON.parse(e.postData.contents);
  } catch (error) {
    throw new Error('Invalid JSON request body.');
  }
}

function jsonResponse_(payload) {
  return ContentService
    .createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}
