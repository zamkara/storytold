#!/usr/bin/python3
"""Unprivileged adapter between graphical app updates and Artcraft's package verifier."""
import argparse,json,os,re,subprocess,sys


def run(args,timeout=900):
    result=subprocess.run(args,stdin=subprocess.DEVNULL,capture_output=True,text=True,
                          env={**os.environ,'ARTCRAFT_GUI':'1'},timeout=timeout)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or 'Package operation failed')[-16384:].strip())
    return result.stdout


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['check','install'])
    parser.add_argument('package')
    args=parser.parse_args()
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*',args.package):raise ValueError('Invalid package name')
    if os.geteuid()==0:raise RuntimeError('Run the application as your normal user')
    if args.action=='check':
        data=json.loads(run(['/usr/bin/artcraft','-J',args.package],120))
        if data is not None and (not isinstance(data,dict) or not data.get('version')):
            raise RuntimeError('Invalid native release metadata')
        print(json.dumps(data));return
    run(['/usr/bin/pacman','-Q',args.package],15)
    release=json.loads(run(['/usr/bin/artcraft','-J',args.package],120))
    if release is None:raise RuntimeError('No newer native package is published yet; refresh and try again later')
    run(['/usr/bin/artcraft','-u',args.package])
    remaining=json.loads(run(['/usr/bin/artcraft','-J',args.package],120))
    if remaining is not None:raise RuntimeError('A newer package is still available; the update did not finish')

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
        print(str(error),file=sys.stderr);sys.exit(1)
