<!-- markdownlint-disable MD013 -->
<!-- markdownlint-disable MD024 -->

# Changelog

## [0.95.1-alpha.1](https://github.com/reanahub/reana-workflow-validator/compare/0.95.0-alpha.1...0.95.1-alpha.1) (2026-10-01)


### Build

* **python:** add packaging metadata and lock image dependencies ([#10](https://github.com/reanahub/reana-workflow-validator/issues/10)) ([85b166e](https://github.com/reanahub/reana-workflow-validator/commit/85b166e81b5eeea32bec6c25a489543b4b8a61b7))


### Features

* **cli:** add sandboxed workflow specification loader ([#7](https://github.com/reanahub/reana-workflow-validator/issues/7)) ([a87fae9](https://github.com/reanahub/reana-workflow-validator/commit/a87fae9e838f82a64c9bb94c73691841ff54270d))


### Bug fixes

* **git:** update .gitignore to exclude modules directory ([#5](https://github.com/reanahub/reana-workflow-validator/issues/5)) ([6558431](https://github.com/reanahub/reana-workflow-validator/commit/6558431330ee5cc1b875af22ccff29db84fce7f3))


### Continuous integration

* **black:** add Python formatting checks ([#10](https://github.com/reanahub/reana-workflow-validator/issues/10)) ([8d99736](https://github.com/reanahub/reana-workflow-validator/commit/8d99736d74043a6825be84bf0068688cc8647c43))
* **commitlint:** improve checking of merge commits ([#3](https://github.com/reanahub/reana-workflow-validator/issues/3)) ([412fbda](https://github.com/reanahub/reana-workflow-validator/commit/412fbda4ad3a5301b49c6eb1abb13d0b85343c30))
* **commitlint:** initial release ([efdf36b](https://github.com/reanahub/reana-workflow-validator/commit/efdf36bbba23a577706fea69ca9e50f22574f149))
* **docker:** publish tagged images after successful checks ([#10](https://github.com/reanahub/reana-workflow-validator/issues/10)) ([17a965e](https://github.com/reanahub/reana-workflow-validator/commit/17a965eece8b08ff7892c3b59b94259eaa108c1f))
* **flake8:** add Python lint checks ([#10](https://github.com/reanahub/reana-workflow-validator/issues/10)) ([8ebf1b6](https://github.com/reanahub/reana-workflow-validator/commit/8ebf1b6ba160c634a8825e5f98868faf479a465a))
* **jsonlint:** add JSON lint checks ([#10](https://github.com/reanahub/reana-workflow-validator/issues/10)) ([219e65d](https://github.com/reanahub/reana-workflow-validator/commit/219e65dfc12783c98ee4993166caa46044019b78))
* **markdownlint:** add Markdown linting checks ([#4](https://github.com/reanahub/reana-workflow-validator/issues/4)) ([d9f3f8b](https://github.com/reanahub/reana-workflow-validator/commit/d9f3f8bde8f29c5a04b5023a70d5aee815f6a622))
* **prettier:** add Prettier code formatting checks ([#4](https://github.com/reanahub/reana-workflow-validator/issues/4)) ([27289dc](https://github.com/reanahub/reana-workflow-validator/commit/27289dc898b70ee22857dc31192836bb4f18eaf2))
* **pydocstyle:** add Python docstring checks ([#10](https://github.com/reanahub/reana-workflow-validator/issues/10)) ([8b50d5b](https://github.com/reanahub/reana-workflow-validator/commit/8b50d5b048c84b905d78ef41690fe4dcd041ea47))
* **python:** quote test dependency extras ([#10](https://github.com/reanahub/reana-workflow-validator/issues/10)) ([c139a4c](https://github.com/reanahub/reana-workflow-validator/commit/c139a4cf4d7b4262c64b2a09d2a49954a4f2de22))
* **release-please:** initialise release automation ([#10](https://github.com/reanahub/reana-workflow-validator/issues/10)) ([a67e118](https://github.com/reanahub/reana-workflow-validator/commit/a67e118da5954b513326a98b699de673d52bddd6))
* **run-tests:** add usage help and refactor options ([#4](https://github.com/reanahub/reana-workflow-validator/issues/4)) ([8a8e5a2](https://github.com/reanahub/reana-workflow-validator/commit/8a8e5a2df44267c039a1be109bd341d487b5395b))
* **runners:** upgrade CI runners to Ubuntu 24.04 ([#2](https://github.com/reanahub/reana-workflow-validator/issues/2)) ([7252099](https://github.com/reanahub/reana-workflow-validator/commit/7252099aca2798427c75a75d91d3f6325a097451))
* **shfmt:** add shfmt code formatting checks ([#4](https://github.com/reanahub/reana-workflow-validator/issues/4)) ([3181300](https://github.com/reanahub/reana-workflow-validator/commit/31813002b36ee456c634c7e14f6c77a0cbd99324))
* **yamllint:** add YAML linting checks ([#4](https://github.com/reanahub/reana-workflow-validator/issues/4)) ([028207d](https://github.com/reanahub/reana-workflow-validator/commit/028207d2d9bcb8bddfe913dd4f78f616c19afa63))

## 0.95.0-alpha.1

### Features

* Add sandboxed workflow specification loading for Serial, CWL, Yadage and
  Snakemake workflows.
