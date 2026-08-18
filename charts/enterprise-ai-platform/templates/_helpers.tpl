{{/*
Expand the name of the chart.
*/}}
{{- define "enterprise-ai-platform.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "enterprise-ai-platform.fullname" -}}
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
Create chart name and version as used by the chart label.
*/}}
{{- define "enterprise-ai-platform.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "enterprise-ai-platform.labels" -}}
helm.sh/chart: {{ include "enterprise-ai-platform.chart" . }}
{{ include "enterprise-ai-platform.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "enterprise-ai-platform.selectorLabels" -}}
app.kubernetes.io/name: {{ include "enterprise-ai-platform.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "enterprise-ai-platform.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "enterprise-ai-platform.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Backend selector labels
*/}}
{{- define "enterprise-ai-platform.backendSelectorLabels" -}}
app.kubernetes.io/name: {{ include "enterprise-ai-platform.name" . }}
app.kubernetes.io/component: backend
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Frontend selector labels
*/}}
{{- define "enterprise-ai-platform.frontendSelectorLabels" -}}
app.kubernetes.io/name: {{ include "enterprise-ai-platform.name" . }}
app.kubernetes.io/component: frontend
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}