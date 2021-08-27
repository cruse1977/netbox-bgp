import re

from django import forms
from django.conf import settings
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from django.core.validators import RegexValidator
from django.utils.translation import gettext as _

from extras.models import Tag
from tenancy.models import Tenant
from dcim.models import Device, Site
from ipam.models import IPAddress
from ipam.formfields import IPNetworkFormField
from utilities.forms import (
    BootstrapMixin, DynamicModelChoiceField, BulkEditForm,
    DynamicModelMultipleChoiceField, StaticSelect2,
    APISelect, APISelectMultiple, StaticSelect2Multiple, TagFilterField
)
from extras.forms import (
    CustomFieldModelForm, CustomFieldBulkEditForm, CustomFieldFilterForm
)

from .models import (
    ASN, ASNStatusChoices, Community, BGPSession,
    SessionStatusChoices, RoutingPolicy, BGPPeerGroup
)


from django.forms.widgets import TextInput


class ASdotInput(TextInput):
    def _format_value(self, value):
        if not value:
            return 0
        if not re.match(r'^\d+(\.\d+)?$', str(value)):
            return value
        if '.' not in str(value):
            if int(value) > 65535:
                return '{}.{}'.format(value // 65536, value % 65536)
            else:
                return value
        else:
            return int(value.split('.')[0]) * 65536 + int(value.split('.')[0])

    def render(self, name, value, attrs=None, renderer=None):
        nb_settings = settings.PLUGINS_CONFIG.get('netbox_bgp', {})
        asdot = nb_settings.get('asdot', False)
        if asdot:
            value = self._format_value(value)
        return super().render(name, value, attrs, renderer)


class ASNFilterForm(BootstrapMixin, CustomFieldModelForm):
    q = forms.CharField(
        required=False,
        label='Search'
    )
    tenant = DynamicModelChoiceField(
        queryset=Tenant.objects.all(),
        required=False
    )
    status = forms.MultipleChoiceField(
        choices=ASNStatusChoices,
        required=False,
        widget=StaticSelect2Multiple()
    )
    site = DynamicModelChoiceField(
        queryset=Site.objects.all(),
        required=False
    )

    tag = TagFilterField(ASN)

    class Meta:
        model = ASN
        fields = ['q', 'status', 'tenant']


class ASNForm(BootstrapMixin, CustomFieldModelForm):
    number = forms.CharField(
        widget=ASdotInput
    )
    tags = DynamicModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=False
    )
    site = DynamicModelChoiceField(
        queryset=Site.objects.all(),
        required=False
    )
    tenant = DynamicModelChoiceField(
        queryset=Tenant.objects.all(),
        required=False
    )

    def clean_number(self):
        number = self.cleaned_data['number']
        if not re.match(r'^\d+(\.\d+)?$', number):
            raise forms.ValidationError('AS number is invalid.')
        if '.' in str(number):
            if int(number.split('.')[0]) > 65535 or int(number.split('.')[1]) > 65535:
                raise forms.ValidationError('AS number is invalid.')
            number = int(number.split('.')[0]) * 65536 + int(number.split('.')[1])
        else:
            number = int(number)
        return number

    def clean(self):
        cleaned_data = super().clean()
        if self.errors.get('number'):
            return cleaned_data
        number = cleaned_data.get('number')
        tenant = cleaned_data.get('tenant')
        if 'number' in self.changed_data or 'tenant' in self.changed_data:
            if ASN.objects.filter(number=number, tenant=tenant).exists():
                raise forms.ValidationError('AS number with this number and tenant is already exists.')
        return cleaned_data

    class Meta:
        model = ASN
        fields = [
            'number', 'description', 'status', 'site', 'tenant', 'tags',
        ]


class ASNBulkEditForm(BootstrapMixin, CustomFieldBulkEditForm):
    pk = forms.ModelMultipleChoiceField(
        queryset=ASN.objects.all(),
        widget=forms.MultipleHiddenInput
    )
    tenant = DynamicModelChoiceField(
        queryset=Tenant.objects.all(),
        required=False
    )
    description = forms.CharField(
        max_length=200,
        required=False
    )
    status = forms.ChoiceField(
        required=False,
        choices=ASNStatusChoices,
        widget=StaticSelect2()
    )

    class Meta:
        nullable_fields = [
            'tenant', 'description',
        ]


class CommunityForm(BootstrapMixin, forms.ModelForm):
    tags = DynamicModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=False
    )
    tenant = DynamicModelChoiceField(
        queryset=Tenant.objects.all(),
        required=False
    )

    class Meta:
        model = Community
        fields = [
            'value', 'description', 'status', 'tenant', 'tags',
        ]


class CommunityFilterForm(BootstrapMixin, forms.ModelForm):
    q = forms.CharField(
        required=False,
        label='Search'
    )
    tenant = DynamicModelChoiceField(
        queryset=Tenant.objects.all(),
        required=False
    )
    status = forms.MultipleChoiceField(
        choices=ASNStatusChoices,
        required=False,
        widget=StaticSelect2Multiple()
    )
    site = DynamicModelChoiceField(
        queryset=Site.objects.all(),
        required=False
    )

    tag = TagFilterField(Community)

    class Meta:
        model = Community
        fields = ['q', 'status', 'tenant']


class CommunityBulkEditForm(BootstrapMixin, BulkEditForm):
    pk = forms.ModelMultipleChoiceField(
        queryset=Community.objects.all(),
        widget=forms.MultipleHiddenInput
    )
    tenant = DynamicModelChoiceField(
        queryset=Tenant.objects.all(),
        required=False
    )
    description = forms.CharField(
        max_length=200,
        required=False
    )
    status = forms.ChoiceField(
        required=False,
        choices=ASNStatusChoices,
        widget=StaticSelect2()
    )

    class Meta:
        nullable_fields = [
            'tenant', 'description',
        ]


class BGPSessionForm(BootstrapMixin, CustomFieldModelForm):
    name = forms.CharField(
        max_length=64,
        required=True
    )
    tags = DynamicModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=False
    )
    site = DynamicModelChoiceField(
        queryset=Site.objects.all(),
        required=False
    )
    device = DynamicModelChoiceField(
        queryset=Device.objects.all(),
        required=False,
        query_params={
            'site_id': '$site'
        }
    )
    tenant = DynamicModelChoiceField(
        queryset=Tenant.objects.all(),
        required=False
    )
    local_as = DynamicModelChoiceField(
        queryset=ASN.objects.all(),
        query_params={
            'site_id': '$site'
        },
        display_field='number',
        widget=APISelect(
            api_url='/api/plugins/bgp/asn/',
        )

    )
    remote_as = DynamicModelChoiceField(
        queryset=ASN.objects.all(),
        query_params={
            'site_id': '$site'
        },
        display_field='number',
        widget=APISelect(
            api_url='/api/plugins/bgp/asn/',
        )
    )
    local_address = DynamicModelChoiceField(
        queryset=IPAddress.objects.all(),
        display_field='address',
        query_params={
            'device_id': '$device'
        }
    )
    peer_group = DynamicModelChoiceField(
        queryset=BGPPeerGroup.objects.all(),
        required=False,
        widget=APISelect(
            api_url='/api/plugins/bgp/peer-group/',
        )
    )
    import_policies = DynamicModelMultipleChoiceField(
        queryset=RoutingPolicy.objects.all(),
        required=False,
        widget=APISelectMultiple(
            api_url='/api/plugins/bgp/routing-policy/'
        )
    )
    export_policies = DynamicModelMultipleChoiceField(
        queryset=RoutingPolicy.objects.all(),
        required=False,
        widget=APISelectMultiple(
            api_url='/api/plugins/bgp/routing-policy/'
        )
    )

    class Meta:
        model = BGPSession
        fields = [
            'name', 'site', 'device',
            'local_as', 'remote_as', 'local_address', 'remote_address',
            'description', 'status', 'peer_group', 'tenant', 'tags', 'import_policies', 'export_policies'
        ]
        fieldsets = (
            ('Session', ('name', 'site', 'device', 'description', 'status', 'peer_group', 'tenant', 'tags')),
            ('Remote', ('remote_as', 'remote_address')),
            ('Local', ('local_as', 'local_address')),
            ('Policies', ('import_policies', 'export_policies'))
        )


class BGPSessionAddForm(BGPSessionForm):
    remote_address = IPNetworkFormField()

    def clean_remote_address(self):
        try:
            ip = IPAddress.objects.get(address=str(self.cleaned_data['remote_address']))
        except MultipleObjectsReturned:
            ip = IPAddress.objects.filter(address=str(self.cleaned_data['remote_address'])).first()
        except ObjectDoesNotExist:
            ip = IPAddress.objects.create(address=str(self.cleaned_data['remote_address']))
        self.cleaned_data['remote_address'] = ip
        return self.cleaned_data['remote_address']


class BGPSessionFilterForm(BootstrapMixin, CustomFieldModelForm):
    q = forms.CharField(
        required=False,
        label='Search'
    )
    remote_as = DynamicModelMultipleChoiceField(
        queryset=ASN.objects.all(),
        required=False,
        display_field='number',
        widget=APISelectMultiple(
            api_url='/api/plugins/bgp/asn/',
        )
    )
    local_as = DynamicModelMultipleChoiceField(
        queryset=ASN.objects.all(),
        required=False,
        display_field='number',
        widget=APISelectMultiple(
            api_url='/api/plugins/bgp/asn/',
        )
    )
    by_local_address = forms.CharField(
        required=False,
        label='Local Address'
    )
    by_remote_address = forms.CharField(
        required=False,
        label='Remote Address'
    )
    device_id = DynamicModelMultipleChoiceField(
        queryset=Device.objects.all(),
        required=False,
        label=_('Device')
    )
    status = forms.MultipleChoiceField(
        choices=SessionStatusChoices,
        required=False,
        widget=StaticSelect2Multiple()
    )
    peer_group = DynamicModelMultipleChoiceField(
        queryset=BGPPeerGroup.objects.all(),
        required=False,
        widget=APISelectMultiple(
            api_url='/api/plugins/bgp/peer-group/'
        )
    )
    import_policies = DynamicModelMultipleChoiceField(
        queryset=RoutingPolicy.objects.all(),
        required=False,
        widget=APISelectMultiple(
            api_url='/api/plugins/bgp/routing-policy/'
        )
    )
    export_policies = DynamicModelMultipleChoiceField(
        queryset=RoutingPolicy.objects.all(),
        required=False,
        widget=APISelectMultiple(
            api_url='/api/plugins/bgp/routing-policy/'
        )
    )
    tenant = DynamicModelChoiceField(
        queryset=Tenant.objects.all(),
        required=False
    )

    tag = TagFilterField(BGPSession)

    class Meta:
        model = BGPSession
        fields = ['q', 'status', 'device_id', 'remote_as', 'local_as']


class RoutingPolicyFilterForm(BootstrapMixin, CustomFieldModelForm):
    q = forms.CharField(
        required=False,
        label='Search'
    )

    tag = TagFilterField(RoutingPolicy)

    class Meta:
        model = RoutingPolicy
        fields = ['q']


class RoutingPolicyForm(BootstrapMixin, CustomFieldModelForm):
    tags = DynamicModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=False
    )

    class Meta:
        model = RoutingPolicy
        fields = ['name', 'description']


class BGPPeerGroupFilterForm(BootstrapMixin, CustomFieldModelForm):
    q = forms.CharField(
        required=False,
        label='Search'
    )

    tag = TagFilterField(BGPPeerGroup)

    class Meta:
        model = BGPPeerGroup
        fields = ['q']


class BGPPeerGroupForm(BootstrapMixin, CustomFieldModelForm):
    import_policies = DynamicModelMultipleChoiceField(
        queryset=RoutingPolicy.objects.all(),
        required=False,
        widget=APISelectMultiple(
            api_url='/api/plugins/bgp/routing-policy/'
        )
    )
    export_policies = DynamicModelMultipleChoiceField(
        queryset=RoutingPolicy.objects.all(),
        required=False,
        widget=APISelectMultiple(
            api_url='/api/plugins/bgp/routing-policy/'
        )
    )
    tags = DynamicModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=False
    )

    class Meta:
        model = BGPPeerGroup
        fields = ['name', 'description', 'import_policies', 'export_policies', 'tags']
