# markitdown-n8n

A tiny HTTP wrapper around Microsoft's [MarkItDown](https://github.com/microsoft/markitdown), packaged as a
Docker image (auto-built to GHCR via GitHub Actions) and a Helm chart, meant to be called from n8n's
HTTP Request node.

Gives you PDF/Office/HTML conversion, the `markitdown-ocr` plugin and image description wired to your
**local Ollama** vision model (e.g. `qwen2.5vl`), and audio transcription — all from one pod in your cluster.

## Repo layout

```
docker/                  # the FastAPI wrapper + Dockerfile
.github/workflows/       # CI: builds & pushes image to ghcr.io on push to main / tags
helm/markitdown/         # Helm chart to deploy the service to k3s
```

## 1. One-time setup

1. Push this repo to your own GitHub repo.
2. No extra secrets needed — the workflow uses the built-in `GITHUB_TOKEN`, which already has
   `packages: write` permission (granted in the workflow file).
3. Push to `main` (touching anything under `docker/`) or push a `v*.*.*` tag. The Actions workflow builds
   a multi-arch (amd64+arm64) image and pushes it to:

   ```
   ghcr.io/<your-github-username-or-org>/markitdown-svc:latest
   ghcr.io/<your-github-username-or-org>/markitdown-svc:sha-<short-sha>
   ```

4. **Make the package public** (or set up an image pull secret — see below). By default, GHCR packages
   created by Actions are private. Go to your GitHub profile → Packages → `markitdown-svc` → Package
   settings → Change visibility → Public. This avoids needing pull secrets in k3s at all.

## 2. Deploy with Helm

```bash
helm upgrade --install markitdown ./helm/markitdown \
  --namespace n8n --create-namespace \
  --set image.repository=ghcr.io/<your-username>/markitdown-svc \
  --set image.tag=latest \
  --set ollama.baseUrl=http://ollama.ollama.svc.cluster.local:11434/v1 \
  --set ollama.visionModel=qwen2.5vl:7b
```

Adjust `ollama.baseUrl` to match wherever Ollama actually runs in your cluster
(`<service>.<namespace>.svc.cluster.local:11434`). If Ollama is on your host machine rather than in the
cluster, and you're using k3s with the default `k3d`/`containerd` network, you may need something like
`http://host.k3d.internal:11434/v1` — check `helm/markitdown/values.yaml` for all overridable options.

### If the GHCR package is private

```bash
kubectl create secret docker-registry ghcr-creds \
  --docker-server=ghcr.io \
  --docker-username=<gh-username> \
  --docker-password=<gh-pat-with-read:packages-scope> \
  -n n8n

helm upgrade --install markitdown ./helm/markitdown \
  -n n8n \
  --set imagePullSecrets[0].name=ghcr-creds \
  ... (other --set flags as above)
```

### Verify it's running

```bash
kubectl -n n8n port-forward svc/markitdown 8000:8000
curl http://localhost:8000/health
curl -X POST -F "file=@/path/to/test.pdf" http://localhost:8000/convert
```

## 3. Wire it into n8n

1. **Google Drive node** — Download operation, produces binary output.
2. **HTTP Request node**:
   - Method: `POST`
   - URL: `http://markitdown.n8n.svc.cluster.local:8000/convert` (adjust namespace to match `-n` above)
   - Body Content Type: `Form-Data (Multipart)`
   - Add a binary field named `file`, bound to the binary property from the Drive node
3. Downstream, `{{$json.markdown}}` has the converted text.

## Configuration reference (`values.yaml`)

| Key | Purpose |
|---|---|
| `image.repository` / `image.tag` | Your GHCR image |
| `ollama.baseUrl` | OpenAI-compatible Ollama endpoint used for OCR/image description |
| `ollama.visionModel` | Model name exactly as shown by `ollama list` |
| `enablePlugins` | Toggles the `markitdown-ocr` plugin |
| `maxUploadMb` | Rejects uploads over this size |
| `resources` | CPU/memory requests & limits — bump for heavy PDF/OCR workloads |
| `ingress.enabled` | Expose outside the cluster if you want to hit it from outside n8n |

## Notes

- Audio transcription in MarkItDown's `[audio-transcription]` extra generally routes through
  `SpeechRecognition`, which by default calls Google's free web API to actually do the transcription —
  so it isn't fully offline unless you adapt the wrapper to use a local recognizer. Worth checking before
  assuming zero external calls for that specific feature.
- The service only calls `md.convert()` on files n8n itself uploads (not arbitrary user-supplied URLs),
  matching MarkItDown's own guidance to use the narrowest conversion entrypoint on untrusted input.
