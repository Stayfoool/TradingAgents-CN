.PHONY: verify verify-backend verify-services verify-frontend verify-e2e verify-precommit

verify: verify-backend

verify-backend:
	python3 scripts/validation/quality_verify.py --profile backend

verify-services:
	python3 scripts/validation/quality_verify.py --profile services

verify-frontend:
	python3 scripts/validation/quality_verify.py --profile frontend

verify-e2e:
	python3 scripts/validation/quality_verify.py --profile frontend-e2e

verify-precommit:
	python3 scripts/validation/quality_verify.py --profile precommit
