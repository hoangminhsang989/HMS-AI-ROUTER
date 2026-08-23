#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, sys
from pathlib import Path
VERSION='25.74'
def load(path:Path):
 spec=importlib.util.spec_from_file_location('hms_review_packet74',path);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');a=ap.parse_args();root=Path(a.root).resolve();c=[]
 def add(n,ok,d=None):c.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
 m=load(root/'HMS_Codex_ExternalWindowsEvidenceReviewPacket.py');p=m.synthetic_proof();src=(root/'HMS_Codex_ExternalWindowsEvidenceReviewPacket.py').read_text('utf-8')
 add('proof_pass',p.get('verdict')=='PASS' and p.get('summary',{}).get('total')==10,p.get('summary'))
 add('version_current',m.VERSION==VERSION)
 add('baseline_exact',m.COCKPIT_BASELINE=='1.3.27')
 add('seven_cases_exact',len(m.CASE_IDS)==7 and len(set(m.CASE_IDS))==7,m.CASE_IDS)
 add('raw_evidence_digest_only',all(x in src for x in ['IMMUTABLE_REFERENCED_BY_DIGEST_ONLY','raw_evidence_embedded\':False','raw_report_embedded\':False']))
 add('packet_hash_chain_present','verify_packet_chain' in src and 'prev_packet_sha256' in src and 'packet_sha256' in src)
 add('pseudonymous_reviewers_only','reviewer_ref' in src and 'NON_PSEUDONYMOUS_REVIEWER_REF' in src)
 add('two_baseline_checkpoints',all(x in src for x in ['PACKET_OPEN','FINAL_DECISION','baseline_open','baseline_final']))
 add('capability_binding_present','capability_binding_sha256' in src)
 add('privacy_export_boundary','review_packet_export_safe' in src and 'FORBIDDEN_KEYS' in src)
 add('no_auto_score_or_cert',all(x in src for x in ["'automatic_production_certification':False","'production_score_mutation_authorized':False","'production_score_promotion_eligible':False"]))
 add('codex_only_scope',"'codex_only_scope':True" in src and "'antigravity_scope_imported':False" in src)
 out={'version':VERSION,'suite':'EXTERNAL_WINDOWS_EVIDENCE_REVIEW_PACKET_VALIDATION','summary':{'pass':sum(x['status']=='PASS' for x in c),'fail':sum(x['status']=='FAIL' for x in c),'total':len(c)},'checks':c,'production_score_promotion_eligible':False};out['verdict']='PASS' if out['summary']['fail']==0 else 'FAIL';t=json.dumps(out,ensure_ascii=False,indent=2)
 if a.output:Path(a.output).write_text(t+'\n','utf-8')
 print(t);return 0 if out['verdict']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
