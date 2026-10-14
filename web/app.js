'use strict';
let state, token, page = 'dashboard', filter = 'All', query = '', billingTab = 'credits';
let authMode = 'login', authStep = 'email', authEmail = '', authPurpose = 'login';
const main = document.querySelector('#main');
const modal = document.querySelector('#modal');
const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const date = value => new Date(value).toLocaleString('en-IN', {dateStyle:'medium',timeStyle:'short'});
const statusName = value => String(value).replaceAll('_', ' ');
const iconPaths = {
  grid:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  spark:'m12 3 2.6 6.4L21 12l-6.4 2.6L12 21l-2.6-6.4L3 12l6.4-2.6Z',
  video:'M14 8l7-4v16l-7-4 M3 6h11v12H3z',
  notes:'M6 3h12v18H6z M9 7h6 M9 11h6 M9 15h4',
  user:'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M4 21v-2a8 8 0 0 1 16 0v2',
  clock:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M12 7v5l3 2',
  settings:'M12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8 M12 2v3 M12 19v3 M2 12h3 M19 12h3 M5 5l2 2 M17 17l2 2 M5 19l2-2 M17 7l2-2',
  wallet:'M3 6h17v14H3z M3 6V4h14 M16 11h5v4h-5z',
  key:'M14 7a5 5 0 1 1-10 0 5 5 0 0 1 10 0 M12 11l9 9 M17 16l3-3',
  arrow:'M5 12h14 M14 7l5 5-5 5',
  plus:'M12 5v14 M5 12h14',
  upload:'M12 16V3 M7 8l5-5 5 5 M4 16v5h16v-5',
  check:'m5 12 4 4L19 6',
  mail:'M3 5h18v14H3z m0 0 9 7 9-7',
  eye:'M2 12s3-7 10-7 10 7 10 7-3 7-10 7S2 12 2 12 M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
  wave:'M3 10v4 M7 6v12 M11 3v18 M15 7v10 M19 5v14 M23 10v4'
};
const icon = (name) => `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${iconPaths[name] || iconPaths.spark}"/></svg>`;
const button = (label, action, cls = '', data = '', disabled = false) => `<button class="button ${cls}" data-action="${action}" ${data} ${disabled?'disabled':''}>${label}</button>`;
const badge = (label, cls = '') => `<span class="badge ${cls}">${escape(label)}</span>`;
function toast(message, error = false) {
  const el = document.querySelector('#toast'); el.textContent = message;
  el.className = `show ${error?'error':''}`; clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { el.className = ''; }, error ? 10000 : 4500);
}
async function api(path, data) {
  const response = await fetch(path, data ? {method:'POST',headers:{'Content-Type':'application/json','X-Workspace-Token':token},body:JSON.stringify(data)} : {cache:'no-store'});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Request failed.');
  return result;
}
async function refresh() { state = await api('/api/state'); render(); }
function go(destination) { if (location.hash === `#${destination}`) route(); else location.hash = destination; }
function route() { page = location.hash.slice(1) || 'dashboard'; if(page==='keys'){page='dashboard';history.replaceState(null,'','#dashboard');} filter = 'All'; query = ''; render(); }
const meetingCount = () => state.meetings.length;
const notesCount = () => state.meetings.filter(m => m.notes.summary).length;
function stat(label, subtitle, value, symbol) {return `<div class="stat"><div class="stat-top"><small>${label}</small><span class="tile">${icon(symbol)}</span></div><strong>${value}</strong><p>${subtitle}</p></div>`;}
function empty(title, description, action='new-meeting', label='+ Add a meeting') { return `<div class="empty"><span class="empty-icon">${icon('video')}</span><h3>${title}</h3><p>${description}</p>${button(label,action)}</div>`; }
function rows(meetings) {
  return `<div class="meeting-list">${meetings.map(m => `<div class="meeting-row"><span class="dot"></span><div class="meeting-info"><h3>${escape(m.title)}</h3><p>${escape(m.platform)} · ${escape(statusName(m.status))} · consent confirmed</p></div><time>${date(m.created)}</time>${button('Open','open-meeting','small soft',`data-id="${escape(m.id)}"`)}</div>`).join('')}</div>`;
}
function dashboard() {
  const firstName = escape(state.profile.name.split(' ')[0]);
  return `<div class="overview-heading"><div><p class="eyebrow">YOUR WORKSPACE, AT A GLANCE</p><h2>Welcome back, ${firstName}<span class="welcome-dot">.</span></h2><p>A little less admin. A lot more clarity.</p></div><span class="today-label">${icon('clock')}${new Date().toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'})}</span></div>
  <section class="hero"><div class="hero-copy"><span class="hero-pill">${icon('spark')} Your meeting companion</span><h1>Be in the conversation.<br><span class="gradient-text">We'll keep the details.</span></h1><p>Bring your meetings, decisions, and next steps together in one calm, organized workspace.</p><div class="hero-actions">${button('Join meeting ↗','new-meeting')}<a href="#agents" class="hero-link">Meet your agents ${icon('arrow')}</a></div><div class="hero-platforms"><span>Made for your conversations</span><b class="platform-mark google">G</b><b class="platform-mark teams">T</b><b class="platform-mark zoom">${icon('video')}</b><span>Meet · Teams · Zoom</span></div></div><div class="hero-art" aria-hidden="true"><div class="orbit orbit-one"></div><div class="orbit orbit-two"></div><div class="art-spark spark-one">✦</div><div class="art-spark spark-two">✧</div><div class="memory-card"><div class="memory-top"><span class="memory-logo">${icon('wave')}</span><div><strong>Every word, a little clearer.</strong><small>MEET MASTER</small></div><span class="memory-check">${icon('check')}</span></div><div class="waveform">${Array.from({length:29},(_,i)=>`<i class="wave-${i%7}"></i>`).join('')}</div><div class="memory-lines"><span></span><span></span><span></span></div><div class="memory-tags"><span>${icon('check')} Decisions</span><span>${icon('notes')} Next steps</span></div></div><div class="floating-note">${icon('spark')} Less busywork. More momentum.</div></div></section>
  <div class="stats">${stat('TOTAL MEETINGS','Conversations in your workspace',meetingCount(),'video')}${stat('MEETING NOTES','Sessions with saved insights',notesCount(),'notes')}${stat('YOUR AGENTS','Ready to help you focus',state.agents.length,'spark')}</div>
  <div class="dashboard-grid"><section class="panel recent-panel"><div class="section-heading"><div><p class="eyebrow">YOUR CONVERSATIONS</p><h2>Recent Meetings</h2><p>Everything you need to pick up where you left off.</p></div>${button('Import transcript','import-meeting','small secondary')}</div>${meetingCount()?rows(state.meetings.slice(0,5)):empty('Your next great conversation starts here','Add your first meeting and give its best ideas a place to live.')}<a class="panel-footer-link" href="#history">View all meetings ${icon('arrow')}</a></section><section class="panel getting-started"><div class="section-heading"><div><p class="eyebrow">A GREAT PLACE TO START</p><h2>Make it your own</h2><p>Three small steps to better meetings.</p></div></div><a class="setup-step" href="#agents"><span class="step-number ${state.agents.length?'complete':''}">${state.agents.length?icon('check'):'1'}</span><div><strong>Meet your agent</strong><p>Choose how it captures the important details.</p></div>${icon('arrow')}</a><button class="setup-step" data-action="import-meeting"><span class="step-number ${meetingCount()?'complete':''}">${meetingCount()?icon('check'):'2'}</span><div><strong>Bring a conversation</strong><p>Start with a meeting link or a transcript.</p></div>${icon('arrow')}</button><a class="setup-step" href="#history"><span class="step-number">3</span><div><strong>Revisit your meetings</strong><p>Find conversations, decisions and action items.</p></div>${icon('arrow')}</a><div class="privacy-note">${icon('check')}<p>Thoughtful by design.<br><strong>Consent comes first, every time.</strong></p></div></section></div>`;
}
function agentsPage() {
  return `<section class="panel"><div class="section-heading"><div><p class="eyebrow purple">YOUR WORKSPACE</p><h2>Meeting agents</h2><p>${state.agents.length} reusable ${state.agents.length===1?'agent':'agents'} in this workspace.</p></div>${button('+ Create agent','new-agent')}</div>${state.agents.map(a => `<article class="agent-card"><span class="tile">M</span><div class="agent-body">${badge('● ACTIVE')}<h3>${escape(a.name)}</h3><p>${escape(a.description)}</p><div>${a.tags.map(t => `<span class="tag">${escape(t)}</span>`).join('')}</div><p class="agent-count">${state.meetings.filter(m=>m.agent_id===a.id).length} attached meetings · Custom instructions</p></div><div class="agent-actions">${button('Delete','delete-agent','small danger',`data-id="${escape(a.id)}"`)}${button('Edit','edit-agent','small secondary',`data-id="${escape(a.id)}"`)}${button('Connect to meeting','agent-meeting','small',`data-id="${escape(a.id)}"`)}</div></article>`).join('') || empty('Create your first agent','Give it a name and instructions for how to summarize meetings.','new-agent','+ Create agent')}</section>`;
}
function directory(profile = false) {
  const shown = state.meetings.filter(m => (filter==='All' || (filter==='With notes'?!!m.notes.summary : m.platform===filter)) && `${m.title} ${m.transcript} ${JSON.stringify(m.notes)}`.toLowerCase().includes(query.toLowerCase()));
  const account = profile ? `<section class="panel"><div class="section-heading"><div><h2>Linked accounts</h2><p>Connect a meeting provider to capture live sessions.</p></div></div><div class="connected"><span class="tile">◫</span><div><h3>Meeting bot provider</h3><p>Google Meet · Microsoft Teams · Zoom via Recall.ai</p></div>${badge(state.config.recall?'Configured':'Not configured',state.config.recall?'':'neutral')}</div><div class="notice">Calendar OAuth and automatic scheduled joining are not connected in this local version. Add a live meeting by link below.</div></section>` : '';
  return `<h1 class="page-heading">${profile?'Profile':'Meeting History'}</h1>${account}<section class="panel"><div class="section-heading"><div><p class="eyebrow">MEETING DIRECTORY</p><h2>All Meetings</h2><p>Find sessions, search transcript text, and revisit decisions.</p></div>${button('Add to live meeting','new-meeting','secondary')}</div><div class="searchbar"><input id="meeting-search" aria-label="Search meetings and transcripts" placeholder="Search meetings, notes, and transcripts…" value="${escape(query)}">${button('Import transcript','import-meeting','secondary')}</div><div class="filters">${['All','With notes','Google Meet','Microsoft Teams','Zoom','Transcript upload'].map(f=>`<button class="chip ${filter===f?'active':''}" data-action="filter" data-filter="${f}">${f}</button>`).join('')}</div><div id="directory-results">${shown.length?rows(shown):empty('No matching meetings',meetingCount()?'Try another search or filter.':'Your saved and imported meetings will appear here.')}</div></section>`;
}
function billing() {
  return `<h1 class="page-heading">Billing & Wallet</h1><div class="billing-grid"><div class="stat"><small>WALLET BALANCE</small><h2>Not connected</h2><p>Connect a payment provider to enable credit purchases.</p></div><div class="stat"><span class="tile">▤</span><small>MEETINGS SAVED</small><strong>${meetingCount()}</strong><p>Actual workspace sessions</p></div><div class="stat"><span class="tile">✓</span><small>NOTES GENERATED</small><strong>${notesCount()}</strong><p>Sessions with saved notes</p></div></div>
  <div class="tabs">${[['credits','Add Credits'],['history','Billing History'],['activity','Workspace Activity']].map(([id,label])=>`<button data-action="billing-tab" data-tab="${id}" class="${billingTab===id?'active':''}">${label}</button>`).join('')}</div>
  <section class="panel">${billingTab==='credits'?`<div class="section-heading"><div><h2>Add Credits</h2><p>Payment integration is required before accepting a recharge.</p></div>${badge('Not connected','neutral')}</div><label class="field">Add Credits (INR)<input type="number" value="1000" disabled></label><div class="presets">${[100,500,1000,2500,5000].map(n=>button('₹'+n.toLocaleString('en-IN'),'none','secondary','',true)).join('')}</div>${button('Payment provider not configured','none','full','',true)}<div class="notice">This workspace does not collect payments or maintain a paid-credit balance. OpenAI and Recall.ai bill usage through your own provider accounts.</div>`:billingTab==='history'?empty('No billing transactions','No payment provider is connected. A successful payment will never be shown without a verified transaction.','history','View meetings'):meetingCount()?rows(state.meetings):empty('Your activity will appear here','Save a meeting or import a transcript to get started.')}</section>`;
}
function account() {
  const signedIn = state.config.database==='supabase' && state.config.signed_in;
  const name = state.profile.name || state.config.user?.name || 'Your account';
  return `<div class="access-page">
    <header class="access-header"><h1>Account &amp; User Access</h1>${signedIn?button('Logout '+icon('arrow'),'logout'):''}</header>
    <div class="access-grid">
      <section class="panel access-profile" aria-labelledby="access-profile-title">
        <div class="access-section-heading"><span class="access-icon" aria-hidden="true">${icon('user')}</span><div><p class="eyebrow">${signedIn?'SIGNED IN AS':'LOCAL WORKSPACE'}</p><h2 id="access-profile-title">Your Meet Master Account</h2></div></div>
        <div class="access-identity"><span class="access-avatar">${escape(name[0].toUpperCase())}</span><div class="access-identity-copy"><h3>${escape(name)}</h3><p>${signedIn?escape(state.config.user?.email || ''):'Local workspace on this computer'}</p><div class="access-badges">${badge(signedIn?'● Active session':'Local mode',signedIn?'':'neutral')}${badge('Owner','purple')}</div></div></div>
        <hr class="access-divider">
        <div class="access-section-heading"><span class="access-icon" aria-hidden="true">${icon('settings')}</span><div><h2>Profile &amp; Workspace</h2><p>Your details across the workspace.</p></div></div>
        <form data-form="profile" class="form-grid access-profile-form"><label class="field">Full name<input name="name" value="${escape(name)}" autocomplete="name" maxlength="100" required></label><label class="field">Company name<input name="company" value="${escape(state.profile.company || '')}" autocomplete="organization" placeholder="Company or team name" maxlength="100" required></label><div>${button('Save profile ✓','submit')}</div></form>
      </section>
      <section class="panel access-team" aria-labelledby="access-team-title">
        <div class="access-section-heading"><span class="access-icon access-icon-brand" aria-hidden="true">${icon('user')}</span><div><p class="eyebrow">ACCESS</p><h2 id="access-team-title">Team Members</h2><p>Manage collaborators and workspace roles.</p></div></div>
        <div class="access-invite" aria-describedby="team-unavailable"><label class="field">MEMBER NAME<input placeholder="Team member name" disabled></label><label class="field">EMAIL<input type="email" placeholder="member@company.com" disabled></label><label class="field">ROLE<select disabled><option>Editor</option><option>Viewer</option></select></label>${button('+ Add member','none','','',true)}</div>
        <div class="access-team-placeholder"><span class="access-placeholder-icon" aria-hidden="true">${icon('user')}</span><h3>Team access is not available yet</h3><p id="team-unavailable">Invitations and shared roles are not enabled in this workspace.</p></div>
      </section>
    </div>
  </div>`;
}
function docs() {
  const guides = [
    {symbol:'spark',title:'Agents',text:'Choose how your agent takes notes.',href:'#agents',link:'Open agents'},
    {symbol:'upload',title:'Transcripts',text:'Bring a conversation into your workspace.',action:'import-meeting',link:'Import transcript'},
    {symbol:'notes',title:'Meeting notes',text:'Review, search, and export your notes.',href:'#history',link:'View meetings'}
  ];
  return `<div class="guide-page guide-minimal">
    <header class="guide-header"><div><p class="eyebrow">WORKSPACE GUIDE</p><h1>A quick start.</h1><p>Your next step, made simple.</p></div></header>
    <div class="guide-grid">${guides.map(g=>`<article class="guide-card"><span class="guide-icon" aria-hidden="true">${icon(g.symbol)}</span><h2>${g.title}</h2><p>${g.text}</p>${g.href?`<a class="guide-link" href="${g.href}">${g.link} ${icon('arrow')}</a>`:`<button class="guide-link" data-action="${g.action}">${g.link} ${icon('arrow')}</button>`}</article>`).join('')}</div>
    <section class="guide-faq" aria-label="More help"><details><summary>Need a little more help?</summary>
      <details><summary>Recording a meeting</summary><p>Saving a link does not start recording. Open the meeting and choose <strong>Send recording bot</strong> after informing participants. Live capture requires a configured provider.</p></details>
      <details><summary>Creating notes</summary><p>Import a transcript, then extract source lines or generate AI notes when available. Review the result before exporting.</p></details>
      <details><summary>Data and privacy</summary><p>Your records use the configured database. AI notes send transcript text to OpenAI; recording uses Recall.ai. Keep secrets out of transcripts.</p></details>
      <details><summary>Feature availability</summary><p>Calendar sync, automatic joining, team invitations, and payment checkout are not available. Recorded transcripts require a manual refresh from the meeting page.</p></details>
    </details></section>
    <p class="guide-footnote">${icon('check')} Get permission before recording or importing a conversation.</p>
  </div>`;
}
function detail(id) {
  const m = state.meetings.find(x=>x.id===id);
  if (!m) return empty('Meeting not found','Return to your meeting directory.','history','View history');
  const a = state.agents.find(x=>x.id===m.agent_id);
  return `<a href="#history" class="link">← All meetings</a><div class="detail-header"><div><h1>${escape(m.title)}</h1><p class="muted">${escape(m.platform)} · ${date(m.created)}${a?' · '+escape(a.name):''}</p></div><div class="status-line">${badge(statusName(m.status),'neutral')}${badge('Consent confirmed')}</div></div>${m.error?`<div class="notice">${escape(m.error)}</div>`:''}<div class="detail-controls">${m.url?button('Send recording bot','join-bot','',`data-id="${escape(id)}"`,!state.config.recall||!!m.bot_id||['join_requested','join_uncertain'].includes(m.status)):''}${m.bot_id?button('Refresh from provider','sync-meeting','secondary',`data-id="${escape(id)}"`):''}${button('Generate AI notes','summarize','',`data-id="${escape(id)}"`,!state.config.openai||!m.transcript)}${button('Extract source lines','extract','secondary',`data-id="${escape(id)}"`,!m.transcript)}${button('Export notes ↓','export','secondary',`data-id="${escape(id)}"`,!m.notes.summary)}</div>
  ${m.url&&!state.config.recall?`<div class="notice">Meeting link saved. Live joining is unavailable until Recall.ai is configured.</div>`:''}
  <div class="columns"><section class="panel"><div class="section-heading"><div><p class="eyebrow">MEETING MEMORY</p><h2>Summary & next steps</h2></div></div>${m.notes.summary?`<span class="note-label">${escape(m.notes.source)}</span><div class="notes-content">${escape(m.notes.summary)}</div><hr class="divider"><h3>Decisions</h3>${noteList(m.notes.decisions)}<h3>Action items</h3>${noteList(m.notes.actions)}`:`<div class="empty"><span class="empty-icon">✦</span><h3>Ready when you are</h3><p>Add a transcript, then generate notes. Your summary, decisions, and actions will appear here.</p></div>`}</section>
  <section class="panel"><div class="section-heading"><div><p class="eyebrow">SOURCE OF TRUTH</p><h2>Transcript</h2><p>Speaker names and timestamps can remain in the text.</p></div></div><form data-form="transcript" data-id="${escape(id)}" class="form-grid"><label class="field">Meeting transcript<textarea name="transcript" class="transcript" maxlength="120000" required placeholder="Paste your consent-approved meeting transcript…">${escape(m.transcript)}</textarea></label><div>${button('Save transcript','submit','secondary')}</div></form>${m.consent_at?`<p class="subtle">Consent confirmation saved ${date(m.consent_at)}</p>`:''}</section></div>`;
}
function noteList(values) {return values?.length?`<ul class="notes-list">${values.map(v=>`<li>${escape(v)}</li>`).join('')}</ul>`:`<p class="muted">No explicit items identified.</p>`;}
function authPage() {
  const recovery = state.config.password_recovery, step = recovery ? 'reset' : authStep;
  const signup = authMode === 'signup';
  const titles = {email: signup?'Create your Meet Master account':'Welcome back to Meet Master',password:'Welcome back',signup:'Create your Meet Master account',verify:authPurpose==='recovery'?'Reset your password':'Check your inbox',reset:'Choose a new password'};
  const subtitles = {email:signup?'Start with your email to create your workspace.':'Sign in to your AI meeting workspace.',password:'Enter your password to continue.',signup:"Enter your details. We’ll verify your email with a one-time code.",verify:'Enter the verification code sent to your email.',reset:'A fresh password for your Meet Master workspace.'};
  const passwordField = (label, fresh) => `<label class="field">${label}<span class="auth-input password-wrap"><input name="password" type="password" autocomplete="${fresh?'new-password':'current-password'}" minlength="${fresh?8:6}" maxlength="1024" placeholder="${fresh?'At least 8 characters':'Enter password'}" required><button type="button" data-action="password-toggle" aria-label="Show password" aria-pressed="false">${icon('eye')}</button></span></label>`;
  let fields = '';
  if(step==='email') fields=`<label class="field">Email<span class="auth-input email-input">${icon('mail')}<input name="email" type="email" autocomplete="email" maxlength="254" value="${escape(authEmail)}" required placeholder="Enter your email"></span></label>${button('Continue','submit','full')}`;
  else if(step==='password') fields=`${passwordField('Password',false)}<div class="auth-options"><button type="button" data-action="auth-otp">Login with OTP</button><button type="button" data-action="auth-forgot">Forgot password?</button></div>${button('Sign in','submit','full')}`;
  else if(step==='signup') fields=`<label class="field">Full name<input name="name" autocomplete="name" maxlength="100" required placeholder="Enter your full name"></label>${passwordField('Create password',true)}${button('Send verification code','submit','full')}`;
  else if(step==='verify') fields=`<label class="field">Verification code<input class="otp-input" name="code" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}" minlength="6" maxlength="6" required placeholder="Enter 6-digit code"></label>${button('Verify and continue','submit','full')}<div class="auth-options"><button type="button" data-action="auth-resend">Resend code</button><button type="button" data-action="auth-back">Back to sign in</button></div><p class="auth-help">Enter the 6-digit code from your latest email. Check your spam folder if it has not arrived. Wait before requesting a new code.</p>`;
  else fields=`${passwordField('New password',true)}${button('Save new password','submit','full')}`;
  const emailRow = step!=='email'&&step!=='reset'?`<div class="auth-email-row">${icon('check')}<strong>${escape(authEmail)}</strong><button type="button" data-action="auth-change">Change</button></div>`:'';
  const google = !['verify','reset'].includes(step)?`<div class="auth-divider"><span>OR CONTINUE WITH</span></div><button class="google-signin" data-action="auth-google" ${state.config.google_enabled?'':'disabled'}><span class="google-g" aria-hidden="true">G</span>Continue with Google ${icon('arrow')}</button>${state.config.google_enabled?'':'<p class="auth-provider-note">Google sign-in will be available when enabled in Supabase.</p>'}<button class="auth-toggle" data-action="auth-toggle">${signup?'Already have an account? <strong>Sign in</strong>':'Don’t have an account? <strong>Sign up</strong>'}</button>`:'';
  return `<div class="auth-layout"><section class="auth-story"><a class="auth-brand" href="/" aria-label="Meet Master home"><span class="auth-logo">M</span>Meet Master</a><div class="story-orbit orbit-large"></div><div class="story-orbit orbit-small"></div><span class="story-star star-one">✦</span><span class="story-star star-two">✦</span><div class="auth-story-copy"><span class="story-pill">AI MEETING INTELLIGENCE</span><h1>Every meeting becomes<br><span>lasting team memory.</span></h1><p>Capture approved conversations, organize decisions, and turn every discussion into clear next steps.</p><div class="story-features"><span>Live transcription</span><span>Consent-aware</span><span>Action-ready notes</span></div><div class="story-benefits"><div><strong>Real-time</strong><small>Meeting intelligence</small></div><div><strong>Secure</strong><small>Consent-first capture</small></div><div><strong>Ready</strong><small>Searchable outcomes</small></div></div></div><p class="story-footnote">Secure by design · Built for focused teams</p></section><section class="auth-card"><header class="auth-card-heading"><div class="auth-emblem"><span>✦</span><span class="auth-logo">M</span><span>✦</span></div><p class="eyebrow">AGENT ACCESS</p><h2>${titles[step]}</h2><p>${subtitles[step]}</p></header>${location.hash==='#auth-error'?'<p class="auth-inline-error" role="alert">Google sign-in could not finish. Try again and check your provider and redirect URL settings.</p>':''}${emailRow}<form data-form="auth" data-step="${step}" class="form-grid">${fields}</form>${google}<p class="auth-secure">${icon('check')} Your workspace, securely connected.</p></section></div>`;
}
function databaseSetup() {
  return `<section class="panel docs"><p class="eyebrow">CLOUD DATABASE SETUP</p><h1>One step before your workspace is ready</h1><p>${escape(state.config.database_error)}</p><p>Open your Supabase project → <strong>SQL Editor → New query</strong>. Paste the complete setup SQL and choose <strong>Run</strong>.</p><div class="detail-controls"><a class="button secondary" href="/setup.sql" target="_blank" rel="noopener">Open setup SQL ↗</a>${button('Check database again','database-check')}${button('Sign out','logout','secondary')}</div><p>Your local SQLite data is preserved.</p></section>`;
}
function render() {
  if (!state) return;
  document.body.classList.toggle('auth-screen',state.config.database==='supabase' && (!state.config.signed_in || state.config.password_recovery));
  document.querySelector('#org-name').textContent = state.profile.company;
  document.querySelector('#user-name').textContent = state.profile.name;
  document.querySelector('.user-card small').textContent=state.config.database==='supabase'?'Private cloud workspace':'Local workspace owner';
  document.querySelector('#sidebar-count').textContent = `${meetingCount()} ${meetingCount()===1?'meeting':'meetings'}`;
  document.querySelector('#current-page').textContent = ({dashboard:'Overview',agents:'Meeting agents',profile:'Profile',history:'Meeting history',billing:'Billing & wallet',account:'Account',docs:'Workspace guide'})[page] || 'Meeting details';
  document.querySelector('.topbar-avatar').textContent = state.profile.name[0] || 'M';
  document.querySelectorAll('[data-page]').forEach(a=>a.classList.toggle('active',a.dataset.page===(page.startsWith('meeting/')?'history':page)));
  const views = {dashboard,agents:agentsPage,profile:()=>directory(true),history:()=>directory(),billing,account,docs};
  if(state.config.database==='supabase' && (!state.config.signed_in || state.config.password_recovery)){main.innerHTML=authPage();document.querySelector('#current-page').textContent='Sign in';document.title='Meet Master · Sign in';return;}
  if(state.config.database==='supabase' && !state.config.database_ready){main.innerHTML=databaseSetup();document.querySelector('#current-page').textContent='Database setup';return;}
  main.innerHTML = `<div class="mobile-settings"><a href="#billing">Billing</a><a href="#account">Account</a><a href="#docs">Docs</a></div>` + (page.startsWith('meeting/')?detail(page.slice(8)):(views[page]||dashboard)());
  if(state.config.database==='supabase'){
  }
  document.title = `Meet Master · ${page.startsWith('meeting/')?'Meeting':page[0].toUpperCase()+page.slice(1)}`;
}
function showModal(title, body) {
  document.querySelector('#modal-content').innerHTML = `<div class="modal-heading"><h2>${title}</h2><button class="close" data-action="close-modal" aria-label="Close dialog">×</button></div>${body}`;
  modal.showModal();
}
function agentModal(id) {
  const a = state.agents.find(a=>a.id===id) || {name:'',description:'',instructions:'Summarize the discussion accurately. Identify explicit decisions and action items, with owners and deadlines only when stated.',tags:[]};
  showModal(id?'Edit meeting agent':'Create meeting agent',`<form data-form="agent" ${id?`data-id="${escape(id)}"`:''} class="form-grid"><label class="field">Agent name<input name="name" value="${escape(a.name)}" placeholder="General Meeting Assistant" maxlength="100" required></label><label class="field">Description<input name="description" value="${escape(a.description)}" maxlength="500" placeholder="What should this agent focus on?"></label><label class="field">Instructions<textarea name="instructions" maxlength="12000" required>${escape(a.instructions)}</textarea></label><label class="field">Tags (comma separated)<input name="tags" value="${escape(a.tags.join(', '))}" placeholder="Meeting notes, Action items"></label><div class="form-actions">${button('Cancel','close-modal','secondary')}${button(id?'Save agent':'Create agent','submit')}</div></form>`);
}
function meetingModal(importMode=false, agentId='') {
  showModal(importMode?'Import a conversation':'Add a meeting',`<form data-form="meeting" class="form-grid"><label class="field">Meeting title<input name="title" placeholder="e.g. Product team weekly sync" maxlength="200" required></label>${importMode?`<label class="field">Transcript file (.txt)<input id="transcript-file" type="file" accept=".txt,text/plain"></label><label class="field">Transcript<textarea id="import-text" name="transcript" maxlength="120000" required placeholder="Paste your transcript or choose a text file…"></textarea></label>`:`<label class="field">Meeting link<input name="url" type="url" placeholder="https://meet.google.com/abc-defg-hij" maxlength="2048" required></label>`}<label class="field">Meeting agent<select name="agent_id"><option value="">No agent selected</option>${state.agents.map(a=>`<option value="${escape(a.id)}" ${a.id===agentId?'selected':''}>${escape(a.name)}</option>`).join('')}</select></label><label class="consent"><input name="consent" type="checkbox" required><span>I have permission to ${importMode?'process this transcript':'record this meeting'} and have informed participants. ${importMode?'':'Saving this link does not send a bot.'}</span></label><div class="form-actions">${button('Cancel','close-modal','secondary')}${button(importMode?'Import transcript':'Save meeting','submit')}</div></form>`);
}
document.addEventListener('click',async event=>{
  const el=event.target.closest('[data-action]'); if(!el||el.disabled) return;
  const action=el.dataset.action,id=el.dataset.id;
  if(action==='submit') return;
  if(el.closest('form')) event.preventDefault();
  const local={'password-toggle':()=>{const input=el.parentElement.querySelector('input'),show=input.type==='password';input.type=show?'text':'password';el.setAttribute('aria-label',show?'Hide password':'Show password');el.setAttribute('aria-pressed',String(show));},'auth-toggle':()=>{authMode=authMode==='login'?'signup':'login';authStep=authEmail?(authMode==='signup'?'signup':'password'):'email';render();},'auth-change':()=>{authStep='email';render();main.querySelector('input')?.focus();},'auth-back':()=>{authMode='login';authStep=authEmail?'password':'email';render();},'new-agent':()=>agentModal(),'edit-agent':()=>agentModal(id),'new-meeting':()=>meetingModal(),'import-meeting':()=>meetingModal(true),'agent-meeting':()=>meetingModal(false,id),'close-modal':()=>modal.close(),'open-meeting':()=>go('meeting/'+id),'history':()=>go('history'),'filter':()=>{filter=el.dataset.filter;render();},'billing-tab':()=>{billingTab=el.dataset.tab;render();}};
  if(local[action]) return local[action]();
  if(action==='delete-agent'&&!confirm('Delete this agent? Its meeting history will remain.'))return;
  if(action==='join-bot'&&!confirm('Send a recording bot to this meeting now? Participants must know and consent. Recall.ai may charge your provider account.'))return;
  if(action==='summarize'&&!confirm('Send this transcript to OpenAI to generate notes? Your API account may be charged.'))return;
  if(action==='import-local'&&!confirm('Copy the agents, meetings, transcripts, notes and profile from this computer to your signed-in Supabase account? This only works when your cloud workspace is empty.'))return;
  el.disabled=true;
  try {
    if(action==='auth-google'){const result=await api('/api/auth/google',{});location.assign(result.url);return;}
    else if(['auth-otp','auth-forgot','auth-resend'].includes(action)){authPurpose=action==='auth-forgot'?'recovery':action==='auth-otp'?'login':authPurpose;const result=await api('/api/auth/code',{email:authEmail,purpose:authPurpose});authStep='verify';toast(result.message);render();return;}
    else if(action==='logout'){await api('/api/auth/logout',{});authMode='login';authStep='email';authEmail='';toast('Signed out.');}
    else if(action==='database-check'){await refresh();return;}
    else if(action==='import-local'){await api('/api/database/import',{});toast('Local workspace imported successfully.');}
    else if(action==='delete-agent') {await api('/api/agents/delete',{id});toast('Agent deleted.');}
    else if(action==='join-bot') {const result=await api('/api/meetings/join',{id,confirm:true});toast(result.message);}
    else if(action==='sync-meeting') {el.textContent='Refreshing…';const result=await api('/api/meetings/sync',{id});toast(result.message);}
    else if(action==='summarize'||action==='extract') {el.textContent='Generating…';await api('/api/meetings/summarize',{id,ai:action==='summarize'});toast('Notes saved.');}
    else if(action==='export') {
      const m=state.meetings.find(m=>m.id===id),n=m.notes;
      const content=`# ${m.title}\n\n${n.source}\n\n## Summary\n${n.summary}\n\n## Decisions\n${(n.decisions||[]).map(t=>'- '+t).join('\n')}\n\n## Action items\n${(n.actions||[]).map(t=>'- '+t).join('\n')}\n`;
      const url=URL.createObjectURL(new Blob([content],{type:'text/markdown;charset=utf-8'})),link=document.createElement('a');link.href=url;link.download='meeting-notes.md';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }
    await refresh();
  } catch(error) {toast(error.message,true);await refresh().catch(()=>{});}
  finally {el.disabled=false;}
});
document.addEventListener('submit',async event=>{
  const form=event.target.closest('[data-form]');if(!form)return;
  event.preventDefault();const values=Object.fromEntries(new FormData(form));
  const submit=form.querySelector('[data-action="submit"]');submit.disabled=true;
  try {
    if(form.dataset.form==='auth'){
      const step=form.dataset.step;
      if(step==='email'){
        authEmail=values.email.trim();
        authStep=authMode==='signup'?'signup':'password';
        render();main.querySelector('input')?.focus();return;
      }
      const endpoint={password:'login',signup:'signup',verify:'verify',reset:'password'}[step];
      const result=await api('/api/auth/'+endpoint,{...values,email:authEmail,purpose:authPurpose});
      if(form.elements.password)form.elements.password.value='';
      if(result.verification_required){authStep='verify';authPurpose='signup';}
      else if(step==='reset'||step==='password'||(step==='verify'&&authPurpose!=='recovery')){authMode='login';authStep='email';}
      toast(result.message);
    }
    else if(form.dataset.form==='agent'){values.tags=values.tags.split(',').map(t=>t.trim()).filter(Boolean);if(form.dataset.id)values.id=form.dataset.id;await api('/api/agents/save',values);modal.close();toast('Agent saved.');}
    else if(form.dataset.form==='meeting'){values.consent=form.elements.consent.checked;const result=await api('/api/meetings/create',values);modal.close();await refresh();go('meeting/'+result.id);toast('Meeting saved.');return;}
    else if(form.dataset.form==='profile'){await api('/api/profile',values);toast('Profile saved.');}
    else if(form.dataset.form==='transcript'){if(state.meetings.find(m=>m.id===form.dataset.id)?.notes.summary&&!confirm('Saving this transcript clears the previous notes. Continue?'))return;await api('/api/meetings/transcript',{id:form.dataset.id,transcript:values.transcript});toast('Transcript saved.');}
    await refresh();
  } catch(error) {toast(error.message,true);}
  finally {submit.disabled=false;}
});
document.addEventListener('input',event=>{
  if(event.target.id==='meeting-search'){
    query=event.target.value;const position=event.target.selectionStart;render();const input=document.querySelector('#meeting-search');input.focus();input.setSelectionRange(position,position);
  }
});
document.addEventListener('change',async event=>{
  if(event.target.id!=='transcript-file')return;
  const file=event.target.files[0];if(!file)return;
  if(file.size>500000){toast('Choose a text file smaller than 500 KB.',true);return;}
  try{const text=await file.text();if(text.length>120000)throw new Error('Transcript must be under 120,000 characters.');document.querySelector('#import-text').value=text;}catch(error){toast(error.message,true);}
});
window.addEventListener('hashchange',route);
const navIcons={dashboard:'grid',agents:'spark',profile:'user',history:'clock',billing:'wallet',account:'settings',docs:'notes'};
document.querySelectorAll('[data-page]').forEach(link=>{
  const symbol=navIcons[link.dataset.page];
  if(link.closest('.primary-nav'))link.querySelector('span').innerHTML=icon(symbol);
  else link.innerHTML=icon(symbol)+`<span>${escape(link.getAttribute('aria-label'))}</span>`;
});
(async()=>{try{token=(await api('/api/session')).token;state=await api('/api/state');route();}catch(error){main.innerHTML=`<div class="panel"><h2>Could not open workspace</h2><p>${escape(error.message)}</p><p>Check that the local Python server is running, then reload.</p></div>`;}})();

