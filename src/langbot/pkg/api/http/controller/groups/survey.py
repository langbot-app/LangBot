import quart

from .. import group


@group.group_class('survey', '/api/v1/survey')
class SurveyRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/pending', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _get_pending() -> str:
            """Get pending survey for the frontend to display."""
            survey = self.ap.survey.get_pending_survey() if self.ap.survey else None
            return self.success(data={'survey': survey})

        @self.route('/respond', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _respond() -> str:
            """Submit survey response."""
            json_data = await quart.request.json
            survey_id = json_data.get('survey_id')
            answers = json_data.get('answers', {})
            completed = json_data.get('completed', True)

            if not survey_id:
                return self.fail(1, 'survey_id required')

            if self.ap.survey:
                ok = await self.ap.survey.submit_response(survey_id, answers, completed)
                if ok:
                    return self.success()
                return self.fail(2, 'Failed to submit response')
            return self.fail(3, 'Survey not available')

        @self.route('/feedback', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _feedback(user_email: str) -> str:
            """Submit on-demand user feedback from the sidebar."""
            json_data = await quart.request.get_json(silent=True) or {}
            content = str(json_data.get('content', '')).strip()
            attachments = json_data.get('attachments', [])
            page_url = str(json_data.get('page_url', ''))[:2048]
            user_agent = str(json_data.get('user_agent', ''))[:512]

            if not content:
                return self.fail(1, 'content required')
            if len(content) > 5000:
                return self.fail(2, 'content too long')
            if not isinstance(attachments, list):
                return self.fail(3, 'attachments must be an array')
            if len(attachments) > 3:
                return self.fail(4, 'too many attachments')

            normalized_attachments = []
            for item in attachments:
                if not isinstance(item, dict):
                    continue
                data_url = str(item.get('data_url', ''))
                mime_type = str(item.get('mime_type', ''))[:128]
                name = str(item.get('name', ''))[:255]
                if not data_url.startswith('data:image/'):
                    continue
                if len(data_url) > 2_800_000:
                    return self.fail(5, 'attachment too large')
                normalized_attachments.append({'name': name, 'mime_type': mime_type, 'data_url': data_url})

            if self.ap.survey:
                ok = await self.ap.survey.submit_feedback(
                    content=content,
                    attachments=normalized_attachments,
                    page_url=page_url,
                    user_agent=user_agent,
                    user_email=user_email,
                )
                if ok:
                    return self.success()
                return self.fail(6, 'Failed to submit feedback')
            return self.fail(7, 'Survey not available')

        @self.route('/dismiss', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _dismiss() -> str:
            """Dismiss survey."""
            json_data = await quart.request.json
            survey_id = json_data.get('survey_id')

            if not survey_id:
                return self.fail(1, 'survey_id required')

            if self.ap.survey:
                ok = await self.ap.survey.dismiss_survey(survey_id)
                if ok:
                    return self.success()
                return self.fail(2, 'Failed to dismiss')
            return self.fail(3, 'Survey not available')
