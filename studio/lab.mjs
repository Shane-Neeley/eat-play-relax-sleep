const $ = (selector) => document.querySelector(selector);
let report = null;
const selected = new Set();
$('#tempo').addEventListener('input', (event) => { $('#bpm').textContent = `${event.target.value} BPM`; });
function render() {
  const container = $('#candidates');
  container.replaceChildren();
  const query = $('#search').value.toLowerCase();
  for (const item of report?.candidates ?? []) {
    if (!JSON.stringify([item.name,item.common_name,item.reasons]).toLowerCase().includes(query)) continue;
    const card = document.createElement('article'); card.className = 'candidate';
    const label = document.createElement('label');
    const checkbox = document.createElement('input'); checkbox.type = 'checkbox';
    checkbox.checked = selected.has(item.observation_id);
    checkbox.addEventListener('change', () => checkbox.checked ? selected.add(item.observation_id) : selected.delete(item.observation_id));
    label.append(checkbox, ` ${item.common_name || item.name}`);
    const context = document.createElement('p'); context.textContent = `${item.name} · ${item.identification} · ${item.observed_on}`;
    const reasons = document.createElement('p'); reasons.textContent = item.reasons.join(' / ');
    const rights = document.createElement('p'); rights.textContent = item.media.map(m => `${m.kind}: ${m.license_code || 'permission required'} · ${m.reuse}`).join(' / ');
    const link = document.createElement('a'); link.textContent = 'View community observation ↗';
    link.href = `https://www.inaturalist.org/observations/${Number(item.observation_id)}`;
    link.target = '_blank'; link.rel = 'noopener noreferrer';
    card.append(label,context,reasons,rights,link); container.append(card);
  }
}
$('#search').addEventListener('input',render);
$('#report').addEventListener('change', async (event) => {
  const file = event.target.files[0]; if (!file) return;
  try {
    if (file.size > 2000000) throw new Error('Report must be smaller than 2 MB.');
    const candidate = JSON.parse(await file.text());
    if (candidate.schema !== 'eprs.wildlife-scout/v1' || !Array.isArray(candidate.candidates) || candidate.candidates.some(c => !Number.isSafeInteger(c.observation_id) || !Array.isArray(c.reasons) || !Array.isArray(c.media))) throw new Error('Choose a valid EPRS scout report.');
    report = candidate; selected.clear(); render();
    $('#status').textContent = `${report.candidates.length} candidates · retrieved ${report.retrieved_at}. ${report.boundary}`;
  } catch (error) { $('#status').textContent = error.message; }
});
$('#brief').addEventListener('submit', event => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target));
  const brief = {schema:'eprs.workbench-brief/v1',created_at:new Date().toISOString(),...data,tempo:Number(data.tempo),wildlife:(report?.candidates ?? []).filter(c => selected.has(c.observation_id)),review:'Producer must verify sources, render alternatives and review final media before release.'};
  const url = URL.createObjectURL(new Blob([JSON.stringify(brief,null,2)+'\n'],{type:'application/json'}));
  const link = document.createElement('a'); link.href=url; link.download='eprs-production-brief.json'; link.click();
  setTimeout(() => URL.revokeObjectURL(url),1000);
});
