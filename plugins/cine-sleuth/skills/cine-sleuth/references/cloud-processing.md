# Cloud processing and data handling

CineSleuth uses LycheeAILab cloud analysis, not a local-only model. The user must receive a brief upload disclosure and agree before the original video is sent. Confirm the user's right to use the source at the same time; source rights alone do not imply consent to cloud processing.

## What the service receives and saves

- The untouched original video is uploaded directly to LycheeAILab's private Tencent COS bucket using a short-lived signed PUT URL. The Lab API process does not relay the original file.
- Lab records user/task ownership and the storage object key. Video chunks are sent through Lab to the configured analysis provider using native video input.
- Lab saves model analysis results and task records for history and authorized management access. “Private” means access-controlled, not “only the user can ever access it”.
- The Agent-authored final report and evidence remain local by default. Uploading them is optional and requires the user's agreement; refusal does not prevent local delivery or completion of the cloud model-analysis task.
- Signed URLs and credentials must not be printed or persisted in manifests, logs, or reports.

Do not promise automatic deletion, a retention period, exclusive user access, or that media never leaves the user's device; none of these claims is established here. Explain actual data handling if asked. Keep routine progress messages concise rather than repeating infrastructure details.
