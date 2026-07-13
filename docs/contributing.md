This document describes how you can get started with developing tangler.

## Dependencies

* [Python 3.11+](https://www.python.org)
* [uv](https://docs.astral.sh/uv/)
* [just](https://just.systems/man/en/)
* [pre-commit](https://pre-commit.com/)
* [Docker](https://www.docker.com) for security scans

## Setup

For security, use of [pre-commit](https://pre-commit.com) is with [git trailers](https://git-scm.com/docs/git-interpret-trailers) to confirm your local hooks ran. 

Install the hooks, ensuring pre-commit has the right permissions.

```bash
pre-commit install --install-hooks --overwrite -t commit-msg -t pre-commit
```

Task running is done with [just](https://just.systems/man/en/). To see all available commands:

```bash
just -l
```

## Testing

Testing is done with [pytest](https://docs.pytest.org/en/stable/).

```bash
uv run pytest
```

You can run all tests with a single `just` command.

```bash
just test
```

## Releasing

Go to [Releases → Draft a new release](https://github.com/uktrade/cdl/releases/new)

Create a tag for your version (e.g. `v1.2.3`).

Click **Generate release notes** to get a starting point.

Spend time editing the result. Reword entries for clarity, promote anything noteworthy, remove noise, and add any migration notes or caveats the commit log won't surface on its own.

When you are happy with the notes, publish the release.

## Standards

### Code

Python code should be:

* Unit tested, and pass new and existing tests
* Documented via docstrings, in the [Google style](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html)
* Linted and auto-formatted (`just format`)
* Using env files and dotenv for setting environment variables
* Structured as a Python package with `pyproject.toml`
* Using dependencies managed automatically by uv
* Integrated with justfile when relevant
* Documented, for example, `README.md` files where relevant
* Use `scratch/` for ideation and planning you don't want to commit

### Issues

We track features, issues and bugs in GitHub Issues.

> [!NOTE]
> We welcome bug reports and feature requests from all users. Come say hi!

### Security

We expect all contributors to read [DBT's security policy](https://github.com/uktrade/.github/blob/main/SECURITY.md).

We enforce the [DBT GitHub Security Standards](https://github.com/uktrade/github-standards), which include mandatory signed pre-commit runs.

> [!WARNING]
> **Never** commit keys, secrets or passwords to the repo -- even dummies.
> 
> There's **always** a better way to achieve what you need.

### AI

In order to help reviewers prioritise their time appropriately, we expect any use of AI to be declared in your PR comment.

### Actions

In order to avoid supply chain attacks, we [pin all actions in workflows](https://codeql.github.com/codeql-query-help/actions/actions-unpinned-tag/).

When upgrading actions, we expect PR comments to confirm that the new commit is safe. You need to cover:

* That the commit's `action.yml` only uses pinned child actions, if it has children
* That there are no critical security concerns raised in the issues

See [#395](https://github.com/uktrade/matchbox/pull/395) for an example of the due diligence we expect.

> [!WARNING]
> Dependabot is configured to recommend action updates, but we still expect due diligance to be done on its PRs.

You can also use tools like [`wayneashleyberry/gh-act`](https://github.com/wayneashleyberry/gh-act) to help manage this, allowing you to perform the upgrade in a single line:

```bash
gh act update --pin
```

You will still need to independently verify that the new pins are safe.
