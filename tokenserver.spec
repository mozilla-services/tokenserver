%define pyver 26
%define name python%{pyver}-tokenserver
%define pythonname tokenserver
%define version 0.1
%define release 1

Summary: Token Server.
Name: %{name}
Version: %{version}
Release: %{release}
Source0: %{pythonname}-%{version}.tar.gz
License: MPL
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{pythonname}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
BuildArch: noarch
Vendor: Tarek Ziade <tarek@mozilla.com>
Requires: python%{pyver}-m2crypto nginx python%{pyver} python%{pyver}-setuptools python%{pyver}-webob python%{pyver}-paste python%{pyver}-pastedeploy python%{pyver}-sqlalchemy python%{pyver}-mako python%{pyver}-simplejson python%{pyver}-pastescript python%{pyver}-mako python%{pyver}-markupsafe python%{pyver}-chameleon python%{pyver}-jinja2 python%{pyver}-pyramid python%{pyver}-pyramid_jinja2 python%{pyver}-pyramid_debugtoolbar python%{pyver}-repoze.lru python%{pyver}-translationstring python%{pyver}-wsgi_intercept python%{pyver}-zope.component python%{pyver}-zope.deprecation python%{pyver}-zope.event python%{pyver}-zope.interface python%{pyver}-venusian python%{pyver}-unittest2 python%{pyver}-nose python%{pyver}-psutil python%{pyver}-gevent

Url: https://github.com/mozilla/tokenserver

%description
Token Server.


%prep
%setup -n %{pythonname}-%{version} -n %{pythonname}-%{version}

%build
python%{pyver} setup.py build

%install

# the config file
mkdir -p %{buildroot}%{_sysconfdir}/mozilla-services/token
install -m 0644 etc/tokenserver-prod.ini %{buildroot}%{_sysconfdir}/mozilla-services/token/production.ini

# the app
python%{pyver} setup.py install --single-version-externally-managed --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES

%clean
rm -rf $RPM_BUILD_ROOT

%post

%files -f INSTALLED_FILES

%defattr(-,root,root)
