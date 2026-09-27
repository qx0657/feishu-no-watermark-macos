.PHONY: test inspect install verify

test:
	python3 -m unittest discover -s tests -v

inspect:
	python3 -m feishu_patcher inspect

install:
	python3 -m feishu_patcher install --launch --stop

verify:
	python3 -m feishu_patcher verify
