export function incomeRecordKey(record){
  return record.entryMode==="period"
    ? `period:${record.periodStart}:${record.periodEnd}`
    : `day:${record.date}`;
}

export function upsertIncomeRecord(records,record){
  const key=incomeRecordKey(record);
  const existing=records.find(item=>incomeRecordKey(item)===key);
  const usedByAnotherRecord=records.some(item=>item.id===record.id&&incomeRecordKey(item)!==key);
  const nextId=records.reduce((max,item)=>Math.max(max,Number(item.id)||0),0)+1;
  const saved={...record,id:existing?.id??(usedByAnotherRecord?nextId:record.id)};
  return [...records.filter(item=>incomeRecordKey(item)!==key),saved];
}
