"""Typo-squat detection: flag package names suspiciously close to a popular
one but not an exact match -- the "slopsquatting" pattern where an attacker
registers a name an AI model is likely to hallucinate.

The popular-package lists below are a small starter set, not an exhaustive
top-N -- documented as a known limit, same as the firewall's rule set.
"""

# fmt: off
POPULAR_PYPI = frozenset({
    "requests", "numpy", "pandas", "flask", "django", "pytest", "boto3",
    "click", "pyyaml", "setuptools", "wheel", "six", "certifi", "urllib3",
    "idna", "charset-normalizer", "cryptography", "sqlalchemy", "jinja2",
    "markupsafe", "pillow", "scipy", "matplotlib", "torch", "tensorflow",
    "transformers", "fastapi", "uvicorn", "pydantic", "httpx", "aiohttp",
    "beautifulsoup4", "lxml", "redis", "celery", "gunicorn", "typer",
    "rich", "attrs", "packaging", "pip", "virtualenv", "tox", "black",
    "ruff", "mypy", "isort", "coverage", "scikit-learn", "protobuf",
})

POPULAR_NPM = frozenset({
    "react", "react-dom", "lodash", "express", "axios", "chalk",
    "commander", "vue", "webpack", "typescript", "eslint", "prettier",
    "jest", "mocha", "chai", "moment", "dayjs", "uuid", "dotenv", "cors",
    "body-parser", "next", "nuxt", "tailwindcss", "vite", "rollup",
    "jquery", "socket.io", "mongoose", "sequelize", "pg", "mysql2",
    "jsonwebtoken", "bcrypt", "nodemon", "pm2", "yargs", "inquirer",
    "glob", "rimraf", "fs-extra", "colors", "debug", "semver",
})
# fmt: on


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            current[j] = min(
                previous[j] + 1,  # deletion
                current[j - 1] + 1,  # insertion
                previous[j - 1] + cost,  # substitution
            )
        previous = current
    return previous[-1]


def find_typosquat_match(name: str, popular: frozenset[str]) -> str | None:
    """The popular package `name` most plausibly typo-squats, or None.

    An exact match to a popular name is never a typosquat -- it *is* that
    package. Very short names are skipped: at that length almost anything is
    within edit distance 1-2 of *something*, so the signal isn't meaningful.
    """
    name = name.lower()
    if name in popular or len(name) < 4:
        return None

    best_match = None
    best_distance = None
    for candidate in popular:
        distance = _levenshtein(name, candidate)
        # Require a wider relative gap for longer names so genuinely
        # different, similarly-long names (e.g. "black" vs "click") don't
        # produce a flood of coincidental matches.
        threshold = 1 if len(candidate) < 6 else 2
        if 0 < distance <= threshold and (best_distance is None or distance < best_distance):
            best_distance = distance
            best_match = candidate
    return best_match
