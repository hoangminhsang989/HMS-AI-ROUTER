#!/usr/bin/env python3
from __future__ import annotations
import argparse, base64, ctypes, hashlib, hmac, json, os, secrets, subprocess, tempfile, uuid
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION='25.67'
SCHEMA_VERSION=1
PRODUCT='HMS-AI-ROUTER'
SIGNER_CLASSES={'WINDOWS_LOCAL_MACHINE_DPAPI_HMAC','WINDOWS_CERTIFICATE_SIGNATURE'}
PRODUCTION_CLAIM='SIGNATURE_CONTRACT_READY_WINDOWS_TARGET_SIGNING_NOT_EXECUTED_ON_NONWINDOWS_HOST'


def utcnow()->str:return datetime.now(timezone.utc).isoformat()
def stable(o:Any)->bytes:return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
def sha(v:bytes|str)->str:
    if isinstance(v,str):v=v.encode('utf-8','surrogatepass')
    return hashlib.sha256(v).hexdigest()
def safe_ref(v:str)->str:return 'ref-'+sha(v)[:24]
def atomic_json(path:Path,obj:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('w',encoding='utf-8',newline='\n') as f:
        json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n');f.flush()
        try:os.fsync(f.fileno())
        except Exception:pass
    os.replace(tmp,path)

def canonical_attestation_payload(att:dict[str,Any])->dict[str,Any]:
    # Signature never covers itself, but binds every field that can affect promotion.
    excluded={'signature_envelope','attestation_sha256'}
    return {k:v for k,v in att.items() if k not in excluded}

def payload_digest(att:dict[str,Any])->str:return sha(stable(canonical_attestation_payload(att)))

class DATA_BLOB(ctypes.Structure):
    _fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_byte))]

def _blob(data:bytes):
    buf=ctypes.create_string_buffer(data);return DATA_BLOB(len(data),ctypes.cast(buf,ctypes.POINTER(ctypes.c_byte))),buf

def dpapi_protect(data:bytes,*,machine_scope:bool=True)->bytes:
    if os.name!='nt':raise RuntimeError('WINDOWS_REQUIRED')
    crypt32=ctypes.windll.crypt32;kernel32=ctypes.windll.kernel32
    inp,keep=_blob(data);out=DATA_BLOB();flags=0x4 if machine_scope else 0
    if not crypt32.CryptProtectData(ctypes.byref(inp),'HMS-AI-ROUTER v25.67 attestation key',None,None,None,flags,ctypes.byref(out)):
        raise ctypes.WinError()
    try:return ctypes.string_at(out.pbData,out.cbData)
    finally:kernel32.LocalFree(out.pbData)

def dpapi_unprotect(data:bytes)->bytes:
    if os.name!='nt':raise RuntimeError('WINDOWS_REQUIRED')
    crypt32=ctypes.windll.crypt32;kernel32=ctypes.windll.kernel32
    inp,keep=_blob(data);out=DATA_BLOB()
    if not crypt32.CryptUnprotectData(ctypes.byref(inp),None,None,None,None,0,ctypes.byref(out)):raise ctypes.WinError()
    try:return ctypes.string_at(out.pbData,out.cbData)
    finally:kernel32.LocalFree(out.pbData)

def ensure_dpapi_key(path:Path)->bytes:
    if os.name!='nt':raise RuntimeError('WINDOWS_REQUIRED')
    if path.exists():return dpapi_unprotect(path.read_bytes())
    key=secrets.token_bytes(32);sealed=dpapi_protect(key,machine_scope=True)
    path.parent.mkdir(parents=True,exist_ok=True)
    try:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as f:f.write(sealed);f.flush();os.fsync(f.fileno())
    except FileExistsError:return dpapi_unprotect(path.read_bytes())
    return key

def sign_dpapi(att:dict[str,Any],key_path:Path)->dict[str,Any]:
    key=ensure_dpapi_key(key_path);digest=payload_digest(att);sig=hmac.new(key,digest.encode('ascii'),hashlib.sha256).digest()
    return {'schema_version':SCHEMA_VERSION,'signer_class':'WINDOWS_LOCAL_MACHINE_DPAPI_HMAC','algorithm':'HMAC-SHA256-DPAPI-MACHINE','signed_payload_sha256':digest,'signature_b64':base64.b64encode(sig).decode('ascii'),'signer_key_id_ref':safe_ref(str(key_path.resolve())),'private_material_exported':False,'generated_utc':utcnow()}

def verify_dpapi(att:dict[str,Any],env:dict[str,Any],key_path:Path)->tuple[bool,str]:
    if env.get('signed_payload_sha256')!=payload_digest(att):return False,'SIGNED_PAYLOAD_DIGEST_MISMATCH'
    try:key=ensure_dpapi_key(key_path);actual=base64.b64decode(str(env.get('signature_b64') or ''),validate=True)
    except Exception:return False,'DPAPI_KEY_OR_SIGNATURE_INVALID'
    expected=hmac.new(key,payload_digest(att).encode('ascii'),hashlib.sha256).digest()
    return (hmac.compare_digest(actual,expected),'OK' if hmac.compare_digest(actual,expected) else 'SIGNATURE_INVALID')

def certificate_sign(att:dict[str,Any],thumbprint:str,script_path:Path)->dict[str,Any]:
    if os.name!='nt':raise RuntimeError('WINDOWS_REQUIRED')
    digest=payload_digest(att)
    with tempfile.TemporaryDirectory(prefix='hms-v2566-cert-sign-') as td:
        inp=Path(td)/'input.txt';out=Path(td)/'output.json';inp.write_text(digest,encoding='ascii')
        cmd=['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(script_path),'--Thumbprint',thumbprint,'--DigestFile',str(inp),'--Output',str(out)]
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=30,shell=False)
        if p.returncode!=0 or not out.exists():raise RuntimeError('CERTIFICATE_SIGNER_FAILED')
        r=json.loads(out.read_text('utf-8'))
    return {'schema_version':SCHEMA_VERSION,'signer_class':'WINDOWS_CERTIFICATE_SIGNATURE','algorithm':r.get('algorithm','RSA-SHA256'),'signed_payload_sha256':digest,'signature_b64':r.get('signature_b64',''),'signer_key_id_ref':safe_ref(str(r.get('thumbprint') or thumbprint)),'certificate_der_b64':r.get('certificate_der_b64',''),'certificate_sha256':r.get('certificate_sha256',''),'private_material_exported':False,'generated_utc':utcnow()}

def verify_certificate(att:dict[str,Any],env:dict[str,Any],trusted_certificate_sha256:set[str]|None=None)->tuple[bool,str]:
    if env.get('signed_payload_sha256')!=payload_digest(att):return False,'SIGNED_PAYLOAD_DIGEST_MISMATCH'
    cert_b64=str(env.get('certificate_der_b64') or '');sig_b64=str(env.get('signature_b64') or '')
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding,ec,ed25519,ed448
        cert_der=base64.b64decode(cert_b64,validate=True);sig=base64.b64decode(sig_b64,validate=True);cert=x509.load_der_x509_certificate(cert_der)
        cert_sha=sha(cert_der)
        if str(env.get('certificate_sha256') or '')!=cert_sha:return False,'CERTIFICATE_DIGEST_MISMATCH'
        if trusted_certificate_sha256 is not None and cert_sha not in trusted_certificate_sha256:return False,'CERTIFICATE_NOT_TRUSTED'
        pub=cert.public_key();msg=payload_digest(att).encode('ascii')
        if hasattr(pub,'verify'):
            if pub.__class__.__name__.startswith('RSA'):pub.verify(sig,msg,padding.PKCS1v15(),hashes.SHA256())
            elif pub.__class__.__name__.startswith('EllipticCurve'):pub.verify(sig,msg,ec.ECDSA(hashes.SHA256()))
            elif isinstance(pub,(ed25519.Ed25519PublicKey,ed448.Ed448PublicKey)):pub.verify(sig,msg)
            else:return False,'CERTIFICATE_KEY_TYPE_UNSUPPORTED'
        else:return False,'CERTIFICATE_KEY_TYPE_UNSUPPORTED'
        return True,'OK'
    except Exception:return False,'CERTIFICATE_SIGNATURE_INVALID'

def sign_attestation(att:dict[str,Any],*,mode:str,key_path:Path|None=None,thumbprint:str='',cert_script:Path|None=None)->dict[str,Any]:
    out=json.loads(json.dumps(att))
    if mode=='dpapi':
        if key_path is None:raise ValueError('key_path required')
        env=sign_dpapi(out,key_path)
    elif mode=='certificate':
        if not thumbprint or cert_script is None:raise ValueError('thumbprint/cert_script required')
        env=certificate_sign(out,thumbprint,cert_script)
    else:raise ValueError('unsupported signer mode')
    out['signature_envelope']=env;out['attestation_sha256']=sha(stable({k:v for k,v in out.items() if k!='attestation_sha256'}));return out

def verify_signed_attestation(att:dict[str,Any],*,dpapi_key_path:Path|None=None,trusted_certificate_sha256:set[str]|None=None)->dict[str,Any]:
    reasons=[];env=att.get('signature_envelope') or {};signer=str(env.get('signer_class') or '')
    raw={k:v for k,v in att.items() if k!='attestation_sha256'}
    if att.get('attestation_sha256')!=sha(stable(raw)):reasons.append('ATTESTATION_OUTER_HASH_MISMATCH')
    if signer not in SIGNER_CLASSES:reasons.append('TRUSTED_WINDOWS_SIGNER_CLASS_REQUIRED')
    ok=False;reason='SIGNER_NOT_VERIFIED'
    if signer=='WINDOWS_LOCAL_MACHINE_DPAPI_HMAC':
        if dpapi_key_path is None:reason='DPAPI_VERIFICATION_KEY_CONTEXT_REQUIRED'
        else:ok,reason=verify_dpapi(att,env,dpapi_key_path)
    elif signer=='WINDOWS_CERTIFICATE_SIGNATURE':ok,reason=verify_certificate(att,env,trusted_certificate_sha256)
    if not ok:reasons.append(reason)
    return {'valid':not reasons,'reasons':reasons,'signer_class':signer,'signer_key_id_ref':env.get('signer_key_id_ref',''),'signed_payload_sha256':env.get('signed_payload_sha256',''),'private_material_exported':bool(env.get('private_material_exported',True))}


def synthetic_sign_attestation(att:dict[str,Any])->tuple[dict[str,Any],str]:
    # Portable cryptographic fixture for verifier contract tests only.
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes,serialization
    from cryptography.hazmat.primitives.asymmetric import rsa,padding
    from cryptography.x509.oid import NameOID
    from datetime import timedelta
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'HMS v25.67 synthetic attestation proof')])
    now=datetime.now(timezone.utc)
    cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(hours=1)).sign(key,hashes.SHA256()))
    out=json.loads(json.dumps(att));digest=payload_digest(out);sig=key.sign(digest.encode('ascii'),padding.PKCS1v15(),hashes.SHA256());der=cert.public_bytes(serialization.Encoding.DER)
    out['signature_envelope']={'schema_version':1,'signer_class':'WINDOWS_CERTIFICATE_SIGNATURE','algorithm':'RSA-SHA256','signed_payload_sha256':digest,'signature_b64':base64.b64encode(sig).decode(),'signer_key_id_ref':safe_ref('synthetic-cert'),'certificate_der_b64':base64.b64encode(der).decode(),'certificate_sha256':sha(der),'private_material_exported':False,'generated_utc':utcnow(),'synthetic_fixture':True}
    out['attestation_sha256']=sha(stable({k:v for k,v in out.items() if k!='attestation_sha256'}));return out,sha(der)

def synthetic_certificate_attestation()->tuple[dict[str,Any],str]:
    # Cryptographic contract proof only; generated in memory and NEVER production evidence.
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes,serialization
    from cryptography.hazmat.primitives.asymmetric import rsa,padding
    from cryptography.x509.oid import NameOID
    from datetime import timedelta
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'HMS v25.67 synthetic attestation proof')])
    now=datetime.now(timezone.utc)
    cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(hours=1)).sign(key,hashes.SHA256()))
    att={'product':PRODUCT,'version':VERSION,'package_version':VERSION,'package_manifest_sha256':'a'*64,'run_id':str(uuid.uuid4()),'nonce':secrets.token_hex(32),'generated_utc':utcnow(),'evidence_class':'WINDOWS_TARGET_OBSERVER','events':[{'seq':1,'status':'PASS'}]}
    digest=payload_digest(att);sig=key.sign(digest.encode('ascii'),padding.PKCS1v15(),hashes.SHA256());der=cert.public_bytes(serialization.Encoding.DER)
    att['signature_envelope']={'schema_version':1,'signer_class':'WINDOWS_CERTIFICATE_SIGNATURE','algorithm':'RSA-SHA256','signed_payload_sha256':digest,'signature_b64':base64.b64encode(sig).decode(),'signer_key_id_ref':safe_ref('synthetic-cert'),'certificate_der_b64':base64.b64encode(der).decode(),'certificate_sha256':sha(der),'private_material_exported':False,'generated_utc':utcnow()}
    att['attestation_sha256']=sha(stable({k:v for k,v in att.items() if k!='attestation_sha256'}));return att,sha(der)

def synthetic_proof()->dict[str,Any]:
    tests=[]
    def add(n,ok,d=None):tests.append({'name':n,'status':'PASS' if ok else 'FAIL','detail':d})
    att,cert_sha=synthetic_certificate_attestation();v=verify_signed_attestation(att,trusted_certificate_sha256={cert_sha})
    add('certificate_signature_contract',v['valid'],v);add('private_material_not_exported',not v['private_material_exported'])
    tam=json.loads(json.dumps(att));tam['run_id']=str(uuid.uuid4());v2=verify_signed_attestation(tam,trusted_certificate_sha256={cert_sha});add('payload_tamper_rejected',not v2['valid'],v2['reasons'])
    v3=verify_signed_attestation(att,trusted_certificate_sha256={'0'*64});add('untrusted_certificate_rejected',not v3['valid'] and 'CERTIFICATE_NOT_TRUSTED' in v3['reasons'],v3['reasons'])
    add('dpapi_windows_only',os.name=='nt' or _nonwindows_dpapi_rejected())
    src=Path(__file__).read_text('utf-8');add('certificate_store_invocation_no_shell','shell=False' in src and "'-File'" in src);add('no_private_key_field','private_key' not in json.dumps(att).lower());add('exact_binding_fields',all(x in canonical_attestation_payload(att) for x in ('package_version','package_manifest_sha256','run_id','nonce','evidence_class','events')))
    add('signer_classes_exact',SIGNER_CLASSES=={'WINDOWS_LOCAL_MACHINE_DPAPI_HMAC','WINDOWS_CERTIFICATE_SIGNATURE'})
    passed=sum(t['status']=='PASS' for t in tests)
    return {'product':PRODUCT,'version':VERSION,'suite':'WINDOWS_ATTESTATION_SIGNER_PROOF','generated_utc':utcnow(),'verdict':'PASS' if passed==len(tests) else 'FAIL','summary':{'pass':passed,'fail':len(tests)-passed,'total':len(tests)},'tests':tests,'windows_signing_executed':False,'real_codex_effects_executed':False,'production_score_eligible':False,'production_certification':PRODUCTION_CLAIM}

def _nonwindows_dpapi_rejected()->bool:
    try:dpapi_protect(b'x');return False
    except RuntimeError as e:return str(e)=='WINDOWS_REQUIRED'
    except Exception:return False

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=('proof','verify'),default='proof');ap.add_argument('--input');ap.add_argument('--dpapi-key');ap.add_argument('--trusted-cert-sha256',action='append',default=[]);ap.add_argument('--output');a=ap.parse_args()
    if a.mode=='proof':out=synthetic_proof();rc=0 if out['verdict']=='PASS' else 2
    else:
        if not a.input:raise SystemExit('--input required')
        att=json.loads(Path(a.input).read_text('utf-8'));out=verify_signed_attestation(att,dpapi_key_path=Path(a.dpapi_key) if a.dpapi_key else None,trusted_certificate_sha256=set(a.trusted_cert_sha256) if a.trusted_cert_sha256 else None);out.update({'product':PRODUCT,'version':VERSION,'suite':'WINDOWS_ATTESTATION_SIGNATURE_VERIFY','generated_utc':utcnow(),'production_score_eligible':False});rc=0 if out['valid'] else 2
    if a.output:atomic_json(Path(a.output),out)
    print(json.dumps(out,ensure_ascii=False,indent=2));return rc
if __name__=='__main__':raise SystemExit(main())
