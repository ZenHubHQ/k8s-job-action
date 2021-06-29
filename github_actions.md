# Dashboard to gather all last pipelines run per branch 

https://github.com/organizations/ZenHubHQ/settings/installations/15639135
ZenHub Actions Runner Controller

```bash
encoded_key=$(cat ~/Downloads/zenhub-actions-runner-controller.2021-04-14.private-key.pem | base64)
docker run --rm -p 8080:8080 \
 --env GITHUB_ORG=ZenHubHQ --env GITHUB_APPID=106440 \
 --env GITHUB_APP_PRIVATEKEY=${encoded_key} \
 --env GITHUB_APP_CLIENTID=106440 \
 --env GITHUB_APP_CLIENTSECRET=0172ecebd40ad960c7ac511f038313ecdadca1ec \
 --env GITHUB_APP_INSTALLATIONID=15639135 \
  ghcr.io/chriskinsman/github-action-dashboard:edge node index.js
unset encoded_key
```


# events and payload

- on PR, this is the HEAD of the PR

github.event.pull_request
- branch, doesn't exist 

GITHUB_SHA (or github.sha)
- on branch: HEAD of branch (or github.event.head_commit.id)
- on PR: the merge commit or something, doens't represent anything in the git history


So, if ${{ github.event.pull_request }} is empty
- interesting_git_sha=${{ github.sha }}
else
- interesting_git_sha=${{ github.event.pull_request.head.sha  }}


# know more about an event

      - uses: hmarr/debug-action@v2

