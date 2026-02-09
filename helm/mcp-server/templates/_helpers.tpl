{{/*
=============================================================================
_helpers.tpl - Reusable Template Helpers
=============================================================================

This file defines Go template functions that are reused across all templates.
The "_" prefix in the filename tells Helm NOT to render this file as a
Kubernetes manifest — it's only used as a library of helper functions.

Go template basics:
- {{- define "name" }} ... {{ end }}  →  Defines a named template
- {{ include "name" . }}              →  Calls a named template, returns string
- {{- ... }}  (dash before)           →  Trims whitespace BEFORE the output
- {{ ... -}}  (dash after)            →  Trims whitespace AFTER the output
- | nindent 4                         →  Pipes output through "indent 4 spaces
                                         with a leading newline"

The "." (dot) passed to include is the template context — it contains
.Chart, .Release, .Values, etc. Always pass it so helpers can access them.
=============================================================================
*/}}

{{/*
Chart name.
Returns the chart name from Chart.yaml, truncated to 63 characters.

Why 63 characters? Kubernetes resource names must be valid DNS subdomain
names (RFC 1123), which limits them to 63 characters. All our generated
names must respect this limit.
*/}}
{{- define "mcp-server.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Fully qualified app name.
Combines the Helm release name with the chart name to create a unique
identifier for this specific installation.

Examples:
  Release "my-release" + Chart "mcp-server" → "my-release-mcp-server"
  Release "mcp-server" + Chart "mcp-server" → "mcp-server" (no duplication)

The deduplication logic prevents names like "mcp-server-mcp-server" when
the release name matches the chart name (a common pattern).
*/}}
{{- define "mcp-server.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Chart label value.
Returns "<chart-name>-<chart-version>" for the helm.sh/chart label.
This helps identify which chart version created a resource.
*/}}
{{- define "mcp-server.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels.
Applied to ALL resources in the chart. These are the standard Kubernetes
recommended labels (https://kubernetes.io/docs/concepts/overview/working-with-objects/common-labels/).

These labels are used for:
- Identifying resources created by this chart (kubectl get all -l app.kubernetes.io/name=mcp-server)
- Grouping in dashboards and monitoring tools
- Helm's own resource tracking (helm.sh/chart, app.kubernetes.io/managed-by)

Note: These are a SUPERSET of selector labels. Selector labels (below) are
a subset used specifically for Service → Pod matching.
*/}}
{{- define "mcp-server.labels" -}}
helm.sh/chart: {{ include "mcp-server.chart" . }}
{{ include "mcp-server.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels.
A SUBSET of the common labels used specifically in:
  - Deployment spec.selector.matchLabels (which pods belong to this Deployment)
  - Service spec.selector (which pods receive traffic from this Service)

CRITICAL: These labels are IMMUTABLE on a Deployment after creation.
If you change them, you must delete and recreate the Deployment.
That's why they only include stable identifiers (name + instance),
not things that change (like version or chart version).

Why only two labels?
- app.kubernetes.io/name: Identifies the application (e.g., "mcp-server")
- app.kubernetes.io/instance: Identifies this specific installation (the Helm release name)
Together, they uniquely identify pods belonging to this specific deployment.
*/}}
{{- define "mcp-server.selectorLabels" -}}
app.kubernetes.io/name: {{ include "mcp-server.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
