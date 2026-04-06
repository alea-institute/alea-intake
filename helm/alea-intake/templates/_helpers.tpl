{{/*
Expand the name of the chart.
*/}}
{{- define "alea-intake.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "alea-intake.fullname" -}}
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
{{- define "alea-intake.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels.
*/}}
{{- define "alea-intake.labels" -}}
helm.sh/chart: {{ include "alea-intake.chart" . }}
{{ include "alea-intake.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels.
*/}}
{{- define "alea-intake.selectorLabels" -}}
app.kubernetes.io/name: {{ include "alea-intake.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Secret name for database credentials.
*/}}
{{- define "alea-intake.dbSecretName" -}}
{{- if .Values.database.existingSecret }}
{{- .Values.database.existingSecret }}
{{- else }}
{{- include "alea-intake.fullname" . }}-db
{{- end }}
{{- end }}

{{/*
Secret name for application secrets.
*/}}
{{- define "alea-intake.appSecretName" -}}
{{- if .Values.appSecret.existingSecret }}
{{- .Values.appSecret.existingSecret }}
{{- else }}
{{- include "alea-intake.fullname" . }}-app
{{- end }}
{{- end }}
