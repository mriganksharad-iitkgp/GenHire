"""Private helpers shared by the cost-statistics methods (token/cost derivation, parsing, pagination)."""

import datetime
import math
import re
from collections import defaultdict


class CostStatsHelpers:
    def _round_money(self, value):
        return round(float(value or 0.0), 2)

    def _safe_iso(self, dt_val):
        return dt_val.isoformat() if dt_val else None

    def _safe_div(self, num, den):
        return (num / den) if den else 0.0

    def _parse_date(self, date_value, end_of_day=False):
        if not date_value:
            return None

        parsed = None
        try:
            parsed = datetime.datetime.fromisoformat(str(date_value).replace("Z", "+00:00"))
        except Exception:
            try:
                parsed = datetime.datetime.strptime(str(date_value), "%Y-%m-%d")
            except Exception:
                return None

        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(datetime.timezone.utc).replace(tzinfo=None)

        if len(str(date_value)) <= 10:
            parsed = parsed.replace(
                hour=23 if end_of_day else 0,
                minute=59 if end_of_day else 0,
                second=59 if end_of_day else 0,
                microsecond=999999 if end_of_day else 0,
            )

        return parsed

    def _period_window(self, period_value):
        now = datetime.datetime.utcnow()
        normalized_period = (period_value or "month").lower()

        if normalized_period == "week":
            start = now - datetime.timedelta(days=7)
        elif normalized_period == "quarter":
            start = now - datetime.timedelta(days=90)
        elif normalized_period == "year":
            start = now - datetime.timedelta(days=365)
        else:
            normalized_period = "month"
            start = now - datetime.timedelta(days=30)

        return normalized_period, start, now

    def _resolve_timeline_window(self, period='month', start_date=None, end_date=None):
        normalized_period, period_start, period_end = self._period_window(period)
        requested_start = self._parse_date(start_date, end_of_day=False)
        requested_end = self._parse_date(end_date, end_of_day=True) if end_date else None

        if start_date and requested_start is None:
            return None, None, None, {'error': 'Invalid start_date format. Use YYYY-MM-DD.'}, 400

        if end_date and requested_end is None:
            return None, None, None, {'error': 'Invalid end_date format. Use YYYY-MM-DD.'}, 400

        if requested_end is None:
            requested_end = datetime.datetime.utcnow()

        if requested_start:
            period_start = requested_start
            period_end = requested_end
            normalized_period = 'custom'

        if period_start > period_end:
            return None, None, None, {'error': 'Invalid timeline. start_date cannot be after end_date.'}, 400

        return normalized_period, period_start, period_end, None, 200

    def _build_date_range_query(self, base_query, date_fields, start_dt, end_dt):
        if not date_fields:
            return base_query

        date_conditions = [
            {field_name: {"$gte": start_dt, "$lte": end_dt}}
            for field_name in date_fields
        ]

        return {"$and": [base_query, {"$or": date_conditions}]}

    def _extract_numeric(self, value):
        if isinstance(value, (int, float)):
            return float(value)
        return None

    def _extract_usage_metric(self, doc, keys, nested_dict_keys=None):
        nested_dict_keys = nested_dict_keys or []

        for key in keys:
            value = self._extract_numeric(doc.get(key))
            if value is not None:
                return value, 'actual'

        for nested_key in nested_dict_keys:
            nested_value = doc.get(nested_key)
            if not isinstance(nested_value, dict):
                continue
            for key in keys:
                value = self._extract_numeric(nested_value.get(key))
                if value is not None:
                    return value, 'actual'

        return None, 'assumed'

    def _collect_text_fragments(self, value, sink):
        if value is None:
            return

        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                sink.append(normalized)
            return

        if isinstance(value, dict):
            for nested_value in value.values():
                self._collect_text_fragments(nested_value, sink)
            return

        if isinstance(value, list):
            for nested_value in value:
                self._collect_text_fragments(nested_value, sink)
            return

        if isinstance(value, (int, float, bool)):
            sink.append(str(value))

    def _estimate_text_tokens(self, text):
        if not text:
            return 0
        normalized_text = str(text)
        words = len(re.findall(r"\S+", normalized_text))
        chars = len(normalized_text)

        tokens_by_words = words / 0.75
        tokens_by_chars = chars / 4.0
        return int(round(max(tokens_by_words, tokens_by_chars)))

    def _estimate_token_count_from_value(self, value):
        chunks = []
        self._collect_text_fragments(value, chunks)
        if not chunks:
            return 0
        return self._estimate_text_tokens(' '.join(chunks))

    def _parse_datetime_value(self, value):
        if isinstance(value, datetime.datetime):
            return value
        if not isinstance(value, str):
            return None

        raw = value.strip()
        if not raw:
            return None

        for candidate in [raw, raw.replace('Z', '+00:00')]:
            try:
                parsed = datetime.datetime.fromisoformat(candidate)
                if parsed.tzinfo is not None:
                    parsed = parsed.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                return parsed
            except Exception:
                continue

        for fmt in ['%a, %d %b %Y %H:%M:%S %Z', '%a, %d %b %Y %H:%M:%S GMT']:
            try:
                return datetime.datetime.strptime(raw, fmt)
            except Exception:
                continue

        return None

    def _qa_pairs(self, doc):
        if not isinstance(doc, dict):
            return []
        qa_pairs = doc.get('qa_pairs')
        if isinstance(qa_pairs, list) and qa_pairs:
            return qa_pairs

        qa_history = doc.get('qa_history')
        if isinstance(qa_history, list) and qa_history:
            return qa_history

        interview_data = doc.get('interview_data')
        if isinstance(interview_data, list) and interview_data:
            return interview_data

        return []

    def _transcript_messages(self, doc):
        transcript = doc.get('transcript') if isinstance(doc, dict) else None
        if isinstance(transcript, list) and transcript:
            return transcript

        messages = []
        for pair in self._qa_pairs(doc):
            if not isinstance(pair, dict):
                continue

            question = pair.get('question')
            answer = pair.get('answer')

            if isinstance(question, str) and question.strip():
                messages.append({'role': 'assistant', 'text': question})
            if isinstance(answer, str) and answer.strip():
                messages.append({'role': 'user', 'text': answer})

        return messages

    def _transcript_token_usage(self, doc):
        stats = self._interview_token_breakdown(doc)
        prompt_tokens = stats.get('cumulative_prompt_tokens') or 0
        completion_tokens = stats.get('question_tokens') or 0

        if prompt_tokens == 0 and completion_tokens == 0:
            return None, None

        return prompt_tokens, completion_tokens

    def _interview_token_breakdown(self, doc):
        messages = self._transcript_messages(doc)
        if not messages:
            return {
                'question_tokens': 0,
                'answer_tokens': 0,
                'qa_total_tokens': 0,
                'cumulative_prompt_tokens': 0,
            }

        pairs = []
        current_question_tokens = None

        question_roles = {'assistant', 'ai', 'bot', 'interviewer', 'system'}

        for item in messages:
            if not isinstance(item, dict):
                continue

            role = str(item.get('role') or '').strip().lower()
            text = item.get('text')
            if not isinstance(text, str):
                text = item.get('content')
            if not isinstance(text, str):
                continue

            token_count = self._estimate_text_tokens(text)
            if token_count <= 0:
                continue

            if role in question_roles:
                if current_question_tokens is not None:
                    pairs.append((current_question_tokens, 0))
                current_question_tokens = token_count
            else:
                if current_question_tokens is None:
                    pairs.append((0, token_count))
                else:
                    pairs.append((current_question_tokens, token_count))
                    current_question_tokens = None

        if current_question_tokens is not None:
            pairs.append((current_question_tokens, 0))

        question_tokens = sum(question for question, _ in pairs)
        answer_tokens = sum(answer for _, answer in pairs)
        qa_total_tokens = question_tokens + answer_tokens

        running_history = 0
        cumulative_prompt_tokens = 0
        for question, answer in pairs:
            pair_total = question + answer
            cumulative_prompt_tokens += running_history + pair_total
            running_history += pair_total

        return {
            'question_tokens': int(question_tokens),
            'answer_tokens': int(answer_tokens),
            'qa_total_tokens': int(qa_total_tokens),
            'cumulative_prompt_tokens': int(cumulative_prompt_tokens),
        }

    def _transcript_tts_characters(self, doc):
        # Per requested accounting rule, TTS proxy uses total question tokens.
        question_tokens = self._interview_token_breakdown(doc).get('question_tokens') or 0
        return int(question_tokens) if question_tokens > 0 else None

    # Cap on any derived speech duration: no single interview is billed as
    # more than 2 hours of audio. Timestamp-difference fallbacks were removed
    # entirely — wall-clock gaps (a session finalized days later by a sweeper)
    # are NOT audio time and used to produce absurd figures like 853,904 "STT
    # seconds" (₹28k/session) for practice rows with empty transcripts.
    MAX_DERIVED_STT_SECONDS = 2 * 60 * 60

    def _derived_stt_seconds(self, doc):
        # STT seconds are derived only from actual spoken content: answer
        # tokens converted at ~0.4s/token (≈150 wpm). With no transcript there
        # is nothing real to derive — return None so the caller falls back to
        # the small fixed assumption instead of inventing a number.
        answer_tokens = self._interview_token_breakdown(doc).get('answer_tokens') or 0
        if answer_tokens > 0:
            return min(float(answer_tokens) * 0.4, float(self.MAX_DERIVED_STT_SECONDS))

        return None

    def _derive_token_usage_from_doc(self, doc, action_type):
        if not isinstance(doc, dict):
            return None, None

        normalized_action = str(action_type or '').strip().lower()

        interview_stats = self._interview_token_breakdown(doc)

        if normalized_action in {'ai_interview', 'practice_interview'}:
            prompt_tokens = interview_stats.get('cumulative_prompt_tokens') or 0
            completion_tokens = interview_stats.get('question_tokens') or 0
            return (
                int(prompt_tokens) if prompt_tokens > 0 else None,
                int(completion_tokens) if completion_tokens > 0 else None,
            )

        if normalized_action in {'ai_interview_evaluation', 'practice_interview_evaluation'}:
            prompt_tokens = interview_stats.get('qa_total_tokens') or 0
            eval_tokens = self._estimate_token_count_from_value(doc.get('evaluation'))
            return (
                int(prompt_tokens) if prompt_tokens > 0 else None,
                int(eval_tokens) if eval_tokens > 0 else None,
            )

        if normalized_action == 'cv_scoring':
            cv_text = (((doc.get('cv_snapshot') or {}).get('text')) or '').strip()
            jd_text = (((doc.get('jd_snapshot') or {}).get('text')) or '').strip()
            prompt_tokens = self._estimate_text_tokens(f"{cv_text}\n{jd_text}".strip())
            completion_tokens = self._estimate_token_count_from_value(doc.get('cv_score_breakdown'))

            if prompt_tokens <= 0:
                prompt_tokens = None
            if completion_tokens <= 0:
                completion_tokens = None

            return prompt_tokens, completion_tokens

        if normalized_action == 'ai_jd_generation':
            metadata = doc.get('metadata') if isinstance(doc.get('metadata'), dict) else {}
            prompt_text = (metadata.get('prompt_text') or '').strip()
            generated_jd_text = (metadata.get('generated_jd_text') or '').strip()

            if prompt_text or generated_jd_text:
                prompt_tokens = self._estimate_text_tokens(prompt_text)
                completion_tokens = self._estimate_text_tokens(generated_jd_text)
                return (
                    int(prompt_tokens) if prompt_tokens > 0 else None,
                    int(completion_tokens) if completion_tokens > 0 else None,
                )

            prompt_seed = {
                'title': doc.get('title'),
                'department': doc.get('department'),
                'location': doc.get('location'),
                'type': doc.get('type'),
                'experience': doc.get('experience'),
                'salary': doc.get('salary'),
            }
            completion_seed = {
                'description': doc.get('description'),
                'skills': doc.get('skills'),
                'responsibilities': doc.get('responsibilities'),
                'requirements': doc.get('requirements'),
                'benefits': doc.get('benefits'),
            }
            prompt_tokens = self._estimate_token_count_from_value(prompt_seed)
            completion_tokens = self._estimate_token_count_from_value(completion_seed)

            if prompt_tokens <= 0:
                prompt_tokens = None
            if completion_tokens <= 0:
                completion_tokens = None

            return prompt_tokens, completion_tokens

        return None, None

    def _latest_interview_reports_by_application(self, application_ids):
        if self.interviews_collection is None:
            return {}

        ids = [str(app_id) for app_id in application_ids if app_id is not None]
        if not ids:
            return {}

        reports = list(self.interviews_collection.find({'application_id': {'$in': ids}}))
        latest_map = {}

        for report in reports:
            app_id = str(report.get('application_id') or '')
            if not app_id:
                continue

            existing = latest_map.get(app_id)
            report_ts = report.get('updated_at') or report.get('created_at')
            existing_ts = (existing or {}).get('updated_at') or (existing or {}).get('created_at')

            if existing is None or (report_ts and (not existing_ts or report_ts > existing_ts)):
                latest_map[app_id] = report

        return latest_map

    def _merge_application_interview_context(self, app_doc, interview_report):
        if not isinstance(app_doc, dict):
            return app_doc

        if not isinstance(interview_report, dict):
            return app_doc

        merged = dict(app_doc)

        if not merged.get('transcript') and isinstance(interview_report.get('transcript'), list):
            merged['transcript'] = interview_report.get('transcript')

        if not merged.get('qa_pairs') and isinstance(interview_report.get('qa_pairs'), list):
            merged['qa_pairs'] = interview_report.get('qa_pairs')

        if merged.get('evaluation') in [None, '', {}] and isinstance(interview_report.get('evaluation'), dict):
            merged['evaluation'] = interview_report.get('evaluation')

        if merged.get('usage_summary') in [None, '', {}] and isinstance(interview_report.get('usage_summary'), dict):
            merged['usage_summary'] = interview_report.get('usage_summary')

        if merged.get('usage_source') in [None, ''] and interview_report.get('usage_source'):
            merged['usage_source'] = interview_report.get('usage_source')

        usage_doc = interview_report.get('usage') if isinstance(interview_report.get('usage'), dict) else None
        if usage_doc:
            if merged.get('prompt_tokens') is None and usage_doc.get('prompt_tokens') is not None:
                merged['prompt_tokens'] = usage_doc.get('prompt_tokens')
            if merged.get('completion_tokens') is None and usage_doc.get('completion_tokens') is not None:
                merged['completion_tokens'] = usage_doc.get('completion_tokens')

        for dt_key in ['created_at', 'completed_at', 'updated_at']:
            if merged.get(dt_key) is None and interview_report.get(dt_key) is not None:
                merged[dt_key] = interview_report.get(dt_key)

        return merged

    def _extract_evaluation_payload(self, doc):
        if not isinstance(doc, dict):
            return None

        candidates = [
            doc.get('evaluation'),
            doc.get('final_evaluation'),
        ]

        result = doc.get('result')
        if isinstance(result, dict):
            candidates.extend([
                result.get('evaluation'),
                result.get('final_evaluation'),
            ])

        for value in candidates:
            if value in [None, '', {}, []]:
                continue
            return value

        return None

    def _with_evaluation_context(self, doc):
        if not isinstance(doc, dict):
            return doc

        evaluation_payload = self._extract_evaluation_payload(doc)
        if evaluation_payload is None:
            return doc

        if doc.get('evaluation') not in [None, '', {}, []]:
            return doc

        merged = dict(doc)
        merged['evaluation'] = evaluation_payload
        return merged

    def _has_interview_evaluation(self, doc):
        if not isinstance(doc, dict):
            return False

        if self._extract_evaluation_payload(doc) is not None:
            return True

        if doc.get('interview_score') not in [None, '']:
            return True

        if doc.get('final_score') not in [None, '']:
            return True

        status = str(doc.get('status') or '').strip().lower()
        if status in {'interviewed', 'selected', 'screening_cleared', 'rejected', 'completed'}:
            return True

        interview_stats = self._interview_token_breakdown(doc)
        return (interview_stats.get('qa_total_tokens') or 0) > 0

    def _resolve_line_model(self, doc, cfg):
        """Prefer the model actually recorded on the document (usage events,
        usage summaries) over the flat assumption model — the assumption is
        only the last resort for docs that never logged what served them."""
        from interview.core.cost_tracker import CostTracker

        candidates = []
        if isinstance(doc, dict):
            candidates.extend([doc.get('model'), doc.get('llm_model')])
            for nested_key in ('usage', 'usage_summary', 'metadata'):
                nested = doc.get(nested_key)
                if isinstance(nested, dict):
                    candidates.extend([nested.get('model'), nested.get('llm_model')])

        for name in candidates:
            if isinstance(name, str) and name.strip() in CostTracker.PRICING:
                return name.strip()
        return cfg['model']

    def _build_token_cost_line(self, doc, action_type, title, cfg, timestamp_fields, source_id=None, source_meta=None):
        source_meta = source_meta or {}

        from interview.core.cost_tracker import CostTracker, calculate_cost
        pricing = CostTracker.PRICING
        inr_per_usd = 83.0

        prompt_tokens, prompt_source = self._extract_usage_metric(
            doc,
            ['prompt_tokens', 'input_tokens', 'llm_prompt_tokens'],
            nested_dict_keys=['usage', 'token_usage', 'cost_usage']
        )
        completion_tokens, completion_source = self._extract_usage_metric(
            doc,
            ['completion_tokens', 'output_tokens', 'llm_completion_tokens'],
            nested_dict_keys=['usage', 'token_usage', 'cost_usage']
        )

        if str(doc.get('usage_source') or '').strip().lower() == 'assumed':
            prompt_tokens = None
            completion_tokens = None
            prompt_source = 'assumed'
            completion_source = 'assumed'

        if prompt_tokens is not None and prompt_tokens <= 0:
            prompt_tokens = None
            prompt_source = 'assumed'
        if completion_tokens is not None and completion_tokens <= 0:
            completion_tokens = None
            completion_source = 'assumed'

        if prompt_tokens is None or completion_tokens is None:
            derived_prompt_tokens, derived_completion_tokens = self._derive_token_usage_from_doc(doc, action_type)
            if prompt_tokens is None and derived_prompt_tokens is not None:
                prompt_tokens = derived_prompt_tokens
                prompt_source = 'actual'
            if completion_tokens is None and derived_completion_tokens is not None:
                completion_tokens = derived_completion_tokens
                completion_source = 'actual'

        # If stored values look like known defaults, prefer transcript-derived values.
        derived_prompt_tokens, derived_completion_tokens = self._derive_token_usage_from_doc(doc, action_type)
        if (
            derived_prompt_tokens is not None
            and int(prompt_tokens or 0) == int(cfg['prompt_tokens'])
        ):
            prompt_tokens = derived_prompt_tokens
            prompt_source = 'actual'
        if (
            derived_completion_tokens is not None
            and int(completion_tokens or 0) == int(cfg['completion_tokens'])
        ):
            completion_tokens = derived_completion_tokens
            completion_source = 'actual'

        prompt_tokens = int(prompt_tokens if prompt_tokens is not None else cfg['prompt_tokens'])
        completion_tokens = int(completion_tokens if completion_tokens is not None else cfg['completion_tokens'])

        line_model = self._resolve_line_model(doc, cfg)
        rates = pricing.get(line_model, {})
        input_rate = rates.get('input', 0.0)
        output_rate = rates.get('output', 0.0)

        llm_usd = ((prompt_tokens / 1_000_000.0) * input_rate) + ((completion_tokens / 1_000_000.0) * output_rate)
        calculated_cost_inr = llm_usd * inr_per_usd

        actual_llm_usd = None
        if prompt_source == 'actual' or completion_source == 'actual':
            actual_llm_usd = calculate_cost(
                line_model,
                {
                    'prompt_tokens': prompt_tokens,
                    'completion_tokens': completion_tokens,
                },
            )
        actual_cost_inr = (
            self._round_money(actual_llm_usd * inr_per_usd)
            if actual_llm_usd is not None
            else None
        )

        timestamp = None
        for field_name in timestamp_fields:
            dt_val = self._parse_datetime_value(doc.get(field_name))
            if isinstance(dt_val, datetime.datetime):
                timestamp = dt_val
                break

        usage_source = 'actual' if prompt_source == 'actual' or completion_source == 'actual' else 'assumed'

        return {
            'id': str(source_id or doc.get('_id') or ''),
            'action_type': action_type,
            'title': title,
            'timestamp': self._safe_iso(timestamp),
            'model': line_model,
            'usage_source': usage_source,
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'stt_seconds': 0,
            'tts_characters': 0,
            'rates': {
                'input_usd_per_1m_tokens': input_rate,
                'output_usd_per_1m_tokens': output_rate,
            },
            'formula': '((prompt/1M × input_rate) + (completion/1M × output_rate)) × INR conversion',
            'cost_inr': self._round_money(calculated_cost_inr),
            'calculated_cost_inr': self._round_money(calculated_cost_inr),
            'actual_cost_inr': actual_cost_inr,
            'source': {
                'type': source_meta.get('type', ''),
                'id': source_meta.get('id', ''),
                'label': source_meta.get('label', ''),
            }
        }

    def _build_interview_cost_line(self, doc, action_type, title, cfg, timestamp_fields, source_id=None, source_meta=None):
        source_meta = source_meta or {}

        from interview.core.cost_tracker import CostTracker
        pricing = CostTracker.PRICING
        inr_per_usd = 83.0

        prompt_tokens, prompt_source = self._extract_usage_metric(
            doc,
            ['prompt_tokens', 'input_tokens', 'llm_prompt_tokens'],
            nested_dict_keys=['usage', 'token_usage', 'cost_usage']
        )
        completion_tokens, completion_source = self._extract_usage_metric(
            doc,
            ['completion_tokens', 'output_tokens', 'llm_completion_tokens'],
            nested_dict_keys=['usage', 'token_usage', 'cost_usage']
        )
        stt_seconds, stt_source = self._extract_usage_metric(
            doc,
            ['stt_seconds', 'audio_seconds', 'speech_seconds'],
            nested_dict_keys=['usage', 'audio_usage', 'cost_usage']
        )
        tts_characters, tts_source = self._extract_usage_metric(
            doc,
            ['tts_characters', 'character_count', 'tts_chars'],
            nested_dict_keys=['usage', 'audio_usage', 'cost_usage']
        )

        if str(doc.get('usage_source') or '').strip().lower() == 'assumed':
            prompt_tokens = None
            completion_tokens = None
            stt_seconds = None
            tts_characters = None
            prompt_source = 'assumed'
            completion_source = 'assumed'
            stt_source = 'assumed'
            tts_source = 'assumed'

        if prompt_tokens is not None and prompt_tokens <= 0:
            prompt_tokens = None
            prompt_source = 'assumed'
        if completion_tokens is not None and completion_tokens <= 0:
            completion_tokens = None
            completion_source = 'assumed'
        if stt_seconds is not None and stt_seconds <= 0:
            stt_seconds = None
            stt_source = 'assumed'
        if tts_characters is not None and tts_characters <= 0:
            tts_characters = None
            tts_source = 'assumed'

        if prompt_tokens is None or completion_tokens is None:
            derived_prompt_tokens, derived_completion_tokens = self._derive_token_usage_from_doc(doc, action_type)
            if prompt_tokens is None and derived_prompt_tokens is not None:
                prompt_tokens = derived_prompt_tokens
                prompt_source = 'actual'
            if completion_tokens is None and derived_completion_tokens is not None:
                completion_tokens = derived_completion_tokens
                completion_source = 'actual'

        # If stored values look like default assumptions, prefer transcript-derived values.
        derived_prompt_tokens, derived_completion_tokens = self._derive_token_usage_from_doc(doc, action_type)
        if (
            derived_prompt_tokens is not None
            and int(prompt_tokens or 0) == int(cfg['prompt_tokens'])
        ):
            prompt_tokens = derived_prompt_tokens
            prompt_source = 'actual'
        if (
            derived_completion_tokens is not None
            and int(completion_tokens or 0) == int(cfg['completion_tokens'])
        ):
            completion_tokens = derived_completion_tokens
            completion_source = 'actual'

        if stt_seconds is None:
            derived_stt = self._derived_stt_seconds(doc)
            if derived_stt is not None:
                stt_seconds = derived_stt
                stt_source = 'actual'

        derived_stt = self._derived_stt_seconds(doc)
        if (
            derived_stt is not None
            and (stt_seconds is None or float(stt_seconds or 0.0) == float(cfg['stt_seconds']))
        ):
            stt_seconds = derived_stt
            stt_source = 'actual'

        if tts_characters is None:
            derived_tts_chars = self._transcript_tts_characters(doc)
            if derived_tts_chars is not None:
                tts_characters = derived_tts_chars
                tts_source = 'actual'

        derived_tts_chars = self._transcript_tts_characters(doc)
        if (
            derived_tts_chars is not None
            and (tts_characters is None or int(tts_characters or 0) == int(cfg['tts_characters']))
        ):
            tts_characters = derived_tts_chars
            tts_source = 'actual'

        prompt_tokens = int(prompt_tokens if prompt_tokens is not None else cfg['prompt_tokens'])
        completion_tokens = int(completion_tokens if completion_tokens is not None else cfg['completion_tokens'])
        stt_seconds = float(stt_seconds if stt_seconds is not None else cfg['stt_seconds'])
        tts_characters = int(tts_characters if tts_characters is not None else cfg['tts_characters'])
        # Guard against pathological stored values (old docs that recorded
        # wall-clock durations as audio seconds).
        stt_seconds = min(stt_seconds, float(self.MAX_DERIVED_STT_SECONDS))

        line_model = self._resolve_line_model(doc, cfg)
        rates = pricing.get(line_model, {})
        input_rate = rates.get('input', 0.0)
        output_rate = rates.get('output', 0.0)
        stt_rate_per_15s = pricing.get('gcp_stt', {}).get('default', 0.006)
        tts_rates = pricing.get('gcp_tts', {})
        tts_voice_type = str(doc.get('tts_voice_type') or 'standard').lower()
        tts_rate = tts_rates.get(tts_voice_type, tts_rates.get('standard', 0.000004))

        llm_usd = ((prompt_tokens / 1_000_000.0) * input_rate) + ((completion_tokens / 1_000_000.0) * output_rate)
        stt_billed_units = math.ceil(stt_seconds / 15.0) if stt_seconds > 0 else 0
        stt_usd = stt_billed_units * stt_rate_per_15s
        tts_usd = tts_characters * tts_rate
        calculated_cost_inr = (llm_usd + stt_usd + tts_usd) * inr_per_usd

        actual_llm_usd = None
        usage_summary = doc.get('usage_summary') if isinstance(doc, dict) else None
        if isinstance(usage_summary, dict):
            summary_actual = usage_summary.get('total_actual_cost')
            summary_actual_val = self._extract_numeric(summary_actual)
            if summary_actual_val is not None and summary_actual_val > 0:
                actual_llm_usd = summary_actual_val
        actual_cost_inr = (
            self._round_money((actual_llm_usd + stt_usd + tts_usd) * inr_per_usd)
            if actual_llm_usd is not None
            else None
        )

        timestamp = None
        for field_name in timestamp_fields:
            dt_val = self._parse_datetime_value(doc.get(field_name))
            if isinstance(dt_val, datetime.datetime):
                timestamp = dt_val
                break

        usage_source = 'actual' if 'actual' in [prompt_source, completion_source, stt_source, tts_source] else 'assumed'

        # Face-match similarity (ID card vs interview capture, 0-100) written
        # by the background identity scorer — advisory only, never blocking.
        identity_block = doc.get('identity_verification') if isinstance(doc, dict) else None
        face_match_score = (
            self._extract_numeric((identity_block or {}).get('score'))
            if isinstance(identity_block, dict)
            else None
        )

        return {
            'id': str(source_id or doc.get('_id') or ''),
            'action_type': action_type,
            'title': title,
            'timestamp': self._safe_iso(timestamp),
            'model': line_model,
            'face_match_score': face_match_score,
            'usage_source': usage_source,
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'stt_seconds': stt_seconds,
            'tts_characters': tts_characters,
            'rates': {
                'input_usd_per_1m_tokens': input_rate,
                'output_usd_per_1m_tokens': output_rate,
                'stt_usd_per_15_seconds': stt_rate_per_15s,
                'tts_usd_per_character': tts_rate,
            },
            'formula': '[LLM token cost + STT(ceil(sec/15)×rate) + TTS(chars×rate)] × INR conversion',
            'cost_inr': self._round_money(calculated_cost_inr),
            'calculated_cost_inr': self._round_money(calculated_cost_inr),
            'actual_cost_inr': actual_cost_inr,
            'source': {
                'type': source_meta.get('type', ''),
                'id': source_meta.get('id', ''),
                'label': source_meta.get('label', ''),
            }
        }

    def _action_assumptions(self):
        # Fallback assumptions used ONLY when a document carries no real usage
        # and nothing can be derived from its transcript. All LLM work runs
        # through the provider chain with OpenAI gpt-4o-mini primary
        # (LLM_PROVIDER_PRIORITY), so every action is assumed/priced at
        # gpt-4o-mini rates. Values are deliberately modest — a typical
        # 15-minute session — not worst-case.
        return {
            'cv_scoring': {
                'model': 'gpt-4o-mini',
                'prompt_tokens': 1800,
                'completion_tokens': 600,
            },
            'ai_jd_generation': {
                'model': 'gpt-4o-mini',
                'prompt_tokens': 1500,
                'completion_tokens': 1200,
            },
            'ai_interview': {
                'model': 'gpt-4o-mini',
                'prompt_tokens': 4200,
                'completion_tokens': 2100,
                'stt_seconds': 900,       # 15 min of candidate speech
                'tts_characters': 8000,   # ~10 spoken questions
            },
            'evaluation': {
                'model': 'gpt-4o-mini',
                'prompt_tokens': 1500,
                'completion_tokens': 1000,
            },
        }

    def _find_matching_user_id(self, user_id_map, raw_user_id):
        if raw_user_id is None:
            return None
        user_id_str = str(raw_user_id)
        return user_id_str if user_id_str in user_id_map else None

    def _user_succeeded_incoming_map(self, period_start, period_end, audience='candidate'):
        payments_collection = self.users_collection.database.get_collection('payments')
        plans_collection = self.users_collection.database.get_collection('plans')
        if payments_collection is None:
            return {}

        plans = list(plans_collection.find({})) if plans_collection is not None else []
        plans_by_id = {plan_doc.get("_id"): plan_doc for plan_doc in plans}

        query = {
            '$and': [
                {'status': 'succeeded'},
                {
                    '$or': [
                        {'completed_at': {'$gte': period_start, '$lte': period_end}},
                        {'created_at': {'$gte': period_start, '$lte': period_end}},
                    ]
                }
            ]
        }
        payments = list(payments_collection.find(query))

        incoming_map = defaultdict(float)
        for payment in payments:
            employer_id = payment.get('employer_id')
            if employer_id is None:
                continue

            plan_doc = plans_by_id.get(payment.get('plan_id'))
            snapshot = payment.get('metadata', {}) or {}
            if not plan_doc:
                fallback_snapshot = payment.get('plan_snapshot') or {}
                snapshot = {**fallback_snapshot, **snapshot}

            payment_audience = (
                (plan_doc or {}).get('audience')
                or snapshot.get('owner_type')
                or snapshot.get('audience')
                or 'recruiter'
            )
            if payment_audience not in {'candidate', 'recruiter'}:
                payment_audience = 'recruiter'

            if payment_audience != audience:
                continue

            incoming_map[str(employer_id)] += float((payment.get('amount_paise', 0) or 0) / 100.0)

        return {key: self._round_money(value) for key, value in incoming_map.items()}

    def _active_plan_name_map(self, audience='candidate'):
        subscriptions_collection = self.users_collection.database.get_collection('subscriptions')
        if subscriptions_collection is None:
            return {}

        audience_filter = (
            {'plan_snapshot.audience': 'candidate'}
            if audience == 'candidate'
            else {
                '$or': [
                    {'plan_snapshot.audience': 'recruiter'},
                    {'plan_snapshot.audience': {'$exists': False}},
                ]
            }
        )

        subscriptions = list(subscriptions_collection.find({'status': 'active', '$and': [audience_filter]}).sort('created_at', -1))
        plan_map = {}
        for subscription in subscriptions:
            owner_id = str(subscription.get('employer_id'))
            if owner_id in plan_map:
                continue
            snapshot = subscription.get('plan_snapshot') or {}
            plan_map[owner_id] = snapshot.get('name') or snapshot.get('slug') or 'Free'
        return plan_map

    def _line_category_summary(self, key, title, lines):
        total_cost = sum(float(line.get('cost_inr', 0) or 0.0) for line in lines)
        total_calculated_cost = sum(float(line.get('calculated_cost_inr', line.get('cost_inr', 0)) or 0.0) for line in lines)
        actual_values = [line.get('actual_cost_inr') for line in lines if line.get('actual_cost_inr') is not None]
        total_actual_cost = sum(float(value or 0.0) for value in actual_values)
        count = len(lines)
        return {
            'key': key,
            'title': title,
            'count': count,
            'total_cost_inr': self._round_money(total_cost),
            'total_calculated_cost_inr': self._round_money(total_calculated_cost),
            'total_actual_cost_inr': self._round_money(total_actual_cost) if actual_values else None,
            'avg_cost_inr': self._round_money(self._safe_div(total_cost, count)),
            'avg_calculated_cost_inr': self._round_money(self._safe_div(total_calculated_cost, count)),
            'avg_actual_cost_inr': self._round_money(self._safe_div(total_actual_cost, count)) if actual_values else None,
            'lines': sorted(lines, key=lambda item: item.get('timestamp') or '', reverse=True),
        }

    def _usage_events_collection(self):
        return self.users_collection.database.get_collection('ai_usage_events')

    def _get_usage_events(self, actor_type, actor_id=None, action_types=None, period_start=None, period_end=None):
        events_collection = self._usage_events_collection()
        if events_collection is None:
            return []

        query = {
            'actor_type': actor_type,
        }
        if actor_id is not None:
            query['actor_id'] = str(actor_id)

        if action_types:
            query['action_type'] = {'$in': action_types}

        if period_start and period_end:
            query['occurred_at'] = {'$gte': period_start, '$lte': period_end}

        return list(events_collection.find(query))

    def _search_and_paginate_lines(self, lines, search='', page=1, limit=50):
        normalized_search = (search or '').strip().lower()
        if normalized_search:
            def _matches(line):
                haystack = ' '.join([
                    str(line.get('title') or ''),
                    str(line.get('model') or ''),
                    str((line.get('source') or {}).get('label') or ''),
                    str((line.get('source') or {}).get('type') or ''),
                    str(line.get('formula') or ''),
                ]).lower()
                return normalized_search in haystack

            filtered = [line for line in lines if _matches(line)]
        else:
            filtered = lines

        safe_page = max(1, int(page or 1))
        safe_limit = max(1, min(500, int(limit or 50)))
        total = len(filtered)
        start_index = (safe_page - 1) * safe_limit
        end_index = start_index + safe_limit
        paged = filtered[start_index:end_index]

        return {
            'items': paged,
            'pagination': {
                'page': safe_page,
                'limit': safe_limit,
                'total': total,
                'total_pages': (total + safe_limit - 1) // safe_limit if total > 0 else 0,
                'has_next': end_index < total,
                'has_prev': safe_page > 1,
            }
        }
