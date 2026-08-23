#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
VERSION='25.67';PRODUCT='HMS-AI-ROUTER'

def _load(name:str):
    p=Path(__file__).with_name(name);spec=importlib.util.spec_from_file_location('hms_'+name.replace('.py',''),p);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m

def utcnow():return datetime.now(timezone.utc).isoformat()
def safe_reasons(rs:list[str])->list[str]:return [str(x)[:160] for x in rs[:40]]

def verify_attestation_offline(att:dict[str,Any],trust_store:dict[str,Any],*,expected_package_version:str,expected_manifest_sha256:str,expected_trust_snapshot_sha256:str,seen_run_ids:set[str]|None=None,seen_nonces:set[str]|None=None)->dict[str,Any]:
    signer=_load('HMS_Codex_WindowsAttestationSigner.py');trust=_load('HMS_Codex_AttestationTrustStore.py');gate=_load('HMS_Codex_AttestedEvidencePromotionGate.py')
    reasons=[];snap=trust.trust_snapshot(trust_store)
    if snap.get('trust_snapshot_sha256')!=expected_trust_snapshot_sha256:reasons.append('TRUST_SNAPSHOT_DIGEST_MISMATCH')
    if att.get('trust_snapshot_sha256')!=expected_trust_snapshot_sha256:reasons.append('ATTESTATION_TRUST_SNAPSHOT_MISMATCH')
    env=att.get('signature_envelope') or {};signer_class=str(env.get('signer_class') or '')
    trusted=trust.trusted_certificate_sha256(trust_store)
    base=gate.verify_attestation(att,expected_package_version=expected_package_version,expected_manifest_sha256=expected_manifest_sha256,seen_run_ids=seen_run_ids,seen_nonces=seen_nonces,trusted_certificate_sha256=trusted,dpapi_key_path=None)
    reasons.extend(base.get('reasons') or [])
    cert_sha=str(env.get('certificate_sha256') or '')
    if signer_class=='WINDOWS_CERTIFICATE_SIGNATURE':
        cert_eval=trust.evaluate_certificate(trust_store,cert_sha)
        if not cert_eval.get('trusted'):reasons.extend(cert_eval.get('reasons') or [])
    elif signer_class=='WINDOWS_LOCAL_MACHINE_DPAPI_HMAC':
        reasons.append('DPAPI_LOCAL_MACHINE_CONTEXT_REQUIRED_FOR_OFFLINE_VERIFY')
    else:reasons.append('WINDOWS_SIGNER_REQUIRED')
    # de-duplicate without losing order
    reasons=list(dict.fromkeys(reasons))
    return {'product':PRODUCT,'version':VERSION,'suite':'OFFLINE_ATTESTATION_VERIFY','generated_utc':utcnow(),'valid':not reasons,'reasons':safe_reasons(reasons),'package_version':att.get('package_version'),'trust_snapshot_sha256':expected_trust_snapshot_sha256,'signer_class':signer_class,'signer_key_id_ref':env.get('signer_key_id_ref',''),'machine_fingerprint':att.get('machine_fingerprint',''),'runtime_fingerprint':att.get('runtime_fingerprint',''),'raw_account_identity':False,'raw_credentials':False,'network_required':False,'production_score_eligible':False}

def synthetic_proof()->dict[str,Any]:
    import base64
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes,serialization
    from cryptography.hazmat.primitives.asymmetric import rsa,padding
    from cryptography.x509.oid import NameOID
    from datetime import timedelta
    trust=_load('HMS_Codex_AttestationTrustStore.py');signer=_load('HMS_Codex_WindowsAttestationSigner.py');gate=_load('HMS_Codex_AttestedEvidencePromotionGate.py')
    tests=[]
    def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048);now=datetime.now(timezone.utc);name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'HMS v25.67 offline verifier fixture')])
    cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(days=30)).sign(key,hashes.SHA256()))
    cert_der=cert.public_bytes(serialization.Encoding.DER);cert_sha=signer.sha(cert_der)
    store=trust.empty_store();trust.pin_certificate(store,certificate_sha256=cert_sha,signer_key_id_ref=signer.safe_ref(cert_sha),not_after_utc=(now+timedelta(days=30)).isoformat());snap=trust.trust_snapshot(store)
    att=gate.make_attestation(package_version=VERSION,package_manifest_sha256='a'*64,evidence_class='WINDOWS_TARGET_OBSERVER',events=gate.make_chain([{'phase':'OBSERVE','effect':'auth','crash_window':'','status':'PASS'}]));att['trust_snapshot_sha256']=snap['trust_snapshot_sha256']
    digest=signer.payload_digest(att);sig=key.sign(digest.encode('ascii'),padding.PKCS1v15(),hashes.SHA256());att['signature_envelope']={'schema_version':1,'signer_class':'WINDOWS_CERTIFICATE_SIGNATURE','algorithm':'RSA-SHA256','signed_payload_sha256':digest,'signature_b64':base64.b64encode(sig).decode('ascii'),'signer_key_id_ref':signer.safe_ref(cert_sha),'certificate_der_b64':base64.b64encode(cert_der).decode('ascii'),'certificate_sha256':cert_sha,'private_material_exported':False,'generated_utc':utcnow()};att['attestation_sha256']=signer.sha(signer.stable({k:v for k,v in att.items() if k!='attestation_sha256'}))
    r=verify_attestation_offline(att,store,expected_package_version=VERSION,expected_manifest_sha256='a'*64,expected_trust_snapshot_sha256=snap['trust_snapshot_sha256']);add('valid_pinned_certificate_offline',r['valid'],r['reasons'])
    add('network_not_required',r['network_required'] is False);add('privacy_metadata_only',r['raw_credentials'] is False and r['raw_account_identity'] is False)
    revoked=json.loads(json.dumps(store));trust.revoke_certificate(revoked,'pin-'+cert_sha[:20],'TEST_REVOKE');rr=verify_attestation_offline(att,revoked,expected_package_version=VERSION,expected_manifest_sha256='a'*64,expected_trust_snapshot_sha256=trust.trust_snapshot(revoked)['trust_snapshot_sha256']);add('revoked_signer_rejected',not rr['valid'] and any('REVOKED' in x or 'NOT_TRUSTED' in x for x in rr['reasons']),rr['reasons'])
    wrong=verify_attestation_offline(att,store,expected_package_version='25.66',expected_manifest_sha256='a'*64,expected_trust_snapshot_sha256=snap['trust_snapshot_sha256']);add('mixed_version_rejected',not wrong['valid'] and 'MIXED_PACKAGE_VERSION' in wrong['reasons'])
    wrong_manifest=verify_attestation_offline(att,store,expected_package_version=VERSION,expected_manifest_sha256='b'*64,expected_trust_snapshot_sha256=snap['trust_snapshot_sha256']);add('manifest_mismatch_rejected',not wrong_manifest['valid'] and 'PACKAGE_MANIFEST_DIGEST_MISMATCH' in wrong_manifest['reasons'])
    add('pseudonymous_refs_only',str(r.get('machine_fingerprint','')).startswith('ref-') and str(r.get('runtime_fingerprint','')).startswith('ref-'))
    passed=sum(x['status']=='PASS' for x in tests);return {'product':PRODUCT,'version':VERSION,'suite':'OFFLINE_ATTESTATION_VERIFIER_PROOF','generated_utc':utcnow(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'production_score_eligible':False,'windows_runtime_certified':False}

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=('proof','verify'),default='proof');ap.add_argument('--attestation');ap.add_argument('--trust-store');ap.add_argument('--package-version',default=VERSION);ap.add_argument('--manifest-sha256',default='');ap.add_argument('--trust-snapshot-sha256',default='');ap.add_argument('--output');a=ap.parse_args()
    if a.mode=='proof':out=synthetic_proof();rc=0 if out['verdict']=='PASS' else 2
    else:
        if not a.attestation or not a.trust_store:raise SystemExit('--attestation and --trust-store required')
        out=verify_attestation_offline(json.loads(Path(a.attestation).read_text('utf-8')),json.loads(Path(a.trust_store).read_text('utf-8')),expected_package_version=a.package_version,expected_manifest_sha256=a.manifest_sha256,expected_trust_snapshot_sha256=a.trust_snapshot_sha256);rc=0 if out['valid'] else 2
    if a.output:Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2));return rc
if __name__=='__main__':raise SystemExit(main())
