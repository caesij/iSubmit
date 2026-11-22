from contextlib import ExitStack, nullcontext
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import RequestFactory, SimpleTestCase

from role_management import views


class CombinedPermissionSaveTests(SimpleTestCase):
    def test_access_changes_save_with_permissions_only_when_included(self):
        for included, faculty in [(True, False), (False, False), (True, True)]:
            with self.subTest(included=included, faculty=faculty), ExitStack() as stack:
                role = SimpleNamespace(pk=7, group=Mock(pk=8, name='Reviewer'), is_faculty_role=faculty)
                data = {'action': 'save_permissions', 'role_id': '7', 'can_add_9': 'on'}
                if included:
                    data['include_user_management_access'] = '1'
                request = RequestFactory().post('/roles/', data)
                request.user = SimpleNamespace(is_authenticated=True, is_superuser=True)
                for name in ['ensure_role_permissions', 'ensure_default_user_management_rules']:
                    stack.enter_context(patch.object(views, name))
                roles = stack.enter_context(patch.object(views.Role.objects, 'filter'))
                roles.return_value.values_list.return_value = list(views.ROLE_GROUP_NAMES)
                stack.enter_context(patch.object(views, '_get_selected_role', return_value=role))
                stack.enter_context(patch.object(views, 'normalize_role_permissions', return_value=set()))
                stack.enter_context(patch.object(views, 'get_role_content_type', return_value=SimpleNamespace(pk=1)))
                stack.enter_context(patch.object(views.Permission.objects, 'filter'))
                stack.enter_context(patch.object(views.Group.permissions.through.objects, 'filter'))
                stack.enter_context(patch.object(views.transaction, 'atomic', side_effect=nullcontext))
                stack.enter_context(patch.object(views.messages, 'success'))
                stack.enter_context(patch.object(views, 'get_user_management_target_roles', return_value=[SimpleNamespace(pk=9)]))
                save = stack.enter_context(patch.object(views.RoleUserManagementRule.objects, 'update_or_create'))
                self.assertEqual(views.role_management_view(request).status_code, 302)
                if included and not faculty:
                    self.assertEqual(save.call_args.kwargs['defaults'], {
                        'can_add': True, 'can_edit': False,
                        'can_change_status': False, 'can_unlock': False,
                    })
                else:
                    save.assert_not_called()
