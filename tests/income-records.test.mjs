import assert from "node:assert/strict";
import test from "node:test";
import {upsertIncomeRecord} from "../app/income-records.mjs";

const daily=(id,date,amount)=>({id,date,entryMode:"day",periodStart:date,periodEnd:date,dineIn:amount});

test("daily income for different dates is retained even when draft ids collide",()=>{
  let records=[];
  records=upsertIncomeRecord(records,daily(100,"2026-08-20",1000));
  records=upsertIncomeRecord(records,daily(100,"2026-08-21",2000));
  assert.equal(records.length,2);
  assert.deepEqual(records.map(record=>[record.date,record.dineIn]),[["2026-08-20",1000],["2026-08-21",2000]]);
  assert.equal(new Set(records.map(record=>record.id)).size,2);
});

test("saving the same daily date updates only that date",()=>{
  let records=[daily(1,"2026-08-20",1000),daily(2,"2026-08-21",2000)];
  records=upsertIncomeRecord(records,daily(999,"2026-08-20",1500));
  assert.equal(records.length,2);
  assert.equal(records.find(record=>record.date==="2026-08-20")?.dineIn,1500);
  assert.equal(records.find(record=>record.date==="2026-08-20")?.id,1);
  assert.equal(records.find(record=>record.date==="2026-08-21")?.dineIn,2000);
});

test("period income uses its date range as the update key",()=>{
  const first={...daily(1,"2026-08-24",7000),entryMode:"period",periodStart:"2026-08-18",periodEnd:"2026-08-24"};
  const second={...first,id:2,dineIn:7200};
  const records=upsertIncomeRecord(upsertIncomeRecord([],first),second);
  assert.equal(records.length,1);
  assert.equal(records[0].dineIn,7200);
  assert.equal(records[0].id,1);
});
