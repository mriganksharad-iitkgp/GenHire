// Saved manual/edited questions are the source of truth for their slots.
// Legacy metadata without content keeps its existing plan until opened/edited.
export default function questionDraftConfiguration(current, questions) {
  if (!current || questions.some(q=>!q.content)) return current;
  const groups=['mcq','coding','sql'].map(type=>({type,questions:questions.filter(q=>q.type===type)})).filter(g=>g.questions.length);
  if (!groups.length) return current;
  const existing=current.oa.sections;
  const totals=groups.map(g=>existing.find(s=>s.type===g.type)?.weight||1);
  const total=totals.reduce((sum,n)=>sum+n,0);
  let assigned=0,minutesLeft=current.oa.duration_minutes;
  const sections=groups.map((g,index)=>{
    const weight=index===groups.length-1?100-assigned:Math.max(1,Math.floor(100*totals[index]/total));assigned+=weight;
    const duration_minutes=current.oa.timer_mode==='section'?
      index===groups.length-1?minutesLeft:Math.min(minutesLeft-(groups.length-index-1),Math.max(1,Math.floor(current.oa.duration_minutes*weight/100))):
      existing.find(s=>s.type===g.type)?.duration_minutes||10;
    minutesLeft-=duration_minutes;
    return {type:g.type,count:g.questions.length,difficulty:Object.fromEntries(['easy','medium','hard'].map(d=>[d,g.questions.filter(q=>q.content.difficulty===d).length])),
      marks:g.questions.map(q=>q.content.marks),weight,duration_minutes};
  });
  return {...current,oa:{...current.oa,sections}};
}
