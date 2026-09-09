(()=>{
let checkingLimit=20;
ready=d=>!!d&&d.shopper_status==='ready';
live=d=>!!d&&!['expired','blocked'].includes(String(d.shopper_status||''));
window.showMoreChecking=()=>{checkingLimit+=20;renderDeals()};
renderDeals=function(){
  const pool=S.deals||[];
  const r=pool.filter(d=>d.shopper_status==='ready');
  const e=pool.filter(d=>d.shopper_status==='eligibility_check');
  const allChecking=pool.filter(d=>d.shopper_status==='verifying').sort((a,b)=>Number(b.priority_score||0)-Number(a.priority_score||0));
  const c=allChecking.slice(0,checkingLimit);
  const rv=filtered(r);
  $('#readyN').textContent=r.length;
  $('#checkingN').textContent=allChecking.length;
  $('#cheapN').textContent=r.filter(d=>d.final_price!=null&&Number(d.final_price)<=.5).length;
  $('#freeN').textContent=r.filter(d=>Number(d.final_price)===0).length;
  $('#readyCount').textContent=`${rv.length} shown`;
  $('#readyList').innerHTML=rv.length?rv.map(d=>card(d)).join(''):'<div class="empty">No fully verified offers are ready right now.</div>';
  $('#eligCount').textContent=e.length;
  $('#eligList').innerHTML=e.length?e.map(d=>card(d,'elig')).join(''):'<div class="empty">No eligibility-check offers right now.</div>';
  $('#checkingCount').textContent=`${allChecking.length} total • ${c.length} shown`;
  $('#checkingList').innerHTML=c.length?c.map(d=>card(d,'checking')).join('')+(c.length<allChecking.length?`<button class="action secondary" onclick="showMoreChecking()">Show ${Math.min(20,allChecking.length-c.length)} more</button>`:''):'<div class="empty">Nothing is waiting for verification.</div>';
};
load=async function(){
  try{
    $('#live').textContent='● REFRESHING';
    const [d,p]=await Promise.all([
      sb('coupon_hunt_app_feed','select=*&order=priority_score.desc.nullslast,purchase_expiry.asc.nullslast'),
      sb('coupon_passports','select=*&passport_status=neq.excluded_age&order=purchase_expiry.asc.nullslast')
    ]);
    S.deals=d;
    S.passports=p;
    render();
    $('#live').textContent='● LIVE';
    $('#live').classList.remove('offline');
  }catch(e){
    $('#live').textContent='● SYNC ISSUE';
    $('#live').classList.add('offline');
    $('#readyList').innerHTML=`<div class="empty">Live shopper feed failed: ${esc(e.message)}. No old deal feed substituted.</div>`;
  }
};
setTimeout(()=>load(),50);
})();
