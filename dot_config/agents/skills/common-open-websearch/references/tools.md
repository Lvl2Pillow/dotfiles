# Tools

## `web-search`

Use for:
- Finding current information.
- Comparing multiple public sources.
- Locating candidate URLs before deeper reading.

Returns:
- Structured search results with `title`, `url`, `description`, `source`, and `engine`.

Good follow-up actions:
- Fetch one or more result URLs with `web-fetch`.
- Fetch a GitHub README with `fetchGithubReadme`.

## `web-fetch`

Use for:
- Reading a specific public HTTP(S) page.
- Extracting and sanitizing article or documentation text from a known URL.

Notes:
- Supports Markdown files and normal public pages.
- May fail on pages that require browser cookies or unusual TLS chains.
- Some pages may additionally require browser-assisted fallback; if the issue appears to be browser-only content or blocked request-mode access, check whether Playwright/browser support is available before assuming the fetch path itself is broken.
- Do not assume arbitrary homepages or JS-heavy landing pages will yield readable article text; often it is better to search first and then fetch a more specific result page.
- Do not jump to TLS or environment explanations for an ordinary fetch failure; first try a better source URL, a more stable result, or a clearer page target.

### Failure handling

- If `fetch` fails on a site with a broken certificate chain, only then consider `FETCH_WEB_INSECURE_TLS=true`.

## `fetchGithubReadme`

Use for:
- GitHub repository URLs
- Fetching the README file for fast repository understanding before reading source files.
- DO NOT use this tool to browse source files.

Prefer this over `fetch` when the input is clearly a repository URL.
