"""
Email diagnostics and testing system for FieldVision AI
Provides detailed SendGrid configuration testing and troubleshooting
"""

import os
import logging
from typing import Dict, Any

def run_comprehensive_email_diagnostics() -> Dict[str, Any]:
    """Run comprehensive email diagnostics and return detailed results"""
    
    results = {
        'sendgrid_configured': False,
        'api_key_valid': False,
        'permissions_check': None,
        'sender_verification': None,
        'test_email_result': None,
        'recommendations': []
    }
    
    try:
        # Step 1: Check if SendGrid API key exists
        api_key = os.environ.get('SENDGRID_API_KEY')
        if not api_key:
            results['recommendations'].append({
                'priority': 'high',
                'issue': 'No SendGrid API key found',
                'solution': 'Set SENDGRID_API_KEY environment variable with your SendGrid API key'
            })
            return results
        
        results['sendgrid_configured'] = True
        
        # Step 2: Validate API key format
        if not api_key.startswith('SG.'):
            results['recommendations'].append({
                'priority': 'high',
                'issue': 'Invalid API key format',
                'solution': 'SendGrid API keys should start with "SG." - verify your key is correct'
            })
            return results
        
        results['api_key_valid'] = True
        
        # Step 3: Test SendGrid connection and permissions
        from sendgrid import SendGridAPIClient
        sg = SendGridAPIClient(api_key)
        
        # Test API permissions by checking user info
        try:
            response = sg.client.user.get()
            if response.status_code == 200:
                results['permissions_check'] = 'success'
            else:
                results['permissions_check'] = f'failed_status_{response.status_code}'
                results['recommendations'].append({
                    'priority': 'high',
                    'issue': f'API key permissions test failed (status {response.status_code})',
                    'solution': 'Verify your API key has "Mail Send" permissions in SendGrid dashboard'
                })
        except Exception as e:
            results['permissions_check'] = f'error: {str(e)}'
            results['recommendations'].append({
                'priority': 'high',
                'issue': f'API connection failed: {str(e)}',
                'solution': 'Check your SendGrid API key is active and has proper permissions'
            })
        
        # Step 4: Test sender verification with different sender addresses
        test_senders = [
            'noreply@example.com',
            'test@sandbox.sendgrid.net',  # SendGrid sandbox domain
            'alerts@fieldvision.ai'
        ]
        
        sender_test_results = []
        
        for sender in test_senders:
            try:
                from sendgrid.helpers.mail import Mail
                
                message = Mail(
                    from_email=sender,
                    to_emails='test@example.com',
                    subject='SendGrid Test',
                    html_content='<p>Test email</p>'
                )
                
                # Attempt to send (will show specific error for sender verification)
                response = sg.send(message)
                sender_test_results.append({
                    'sender': sender,
                    'status': response.status_code,
                    'success': response.status_code == 202
                })
                
                if response.status_code == 202:
                    break  # Found working sender
                    
            except Exception as e:
                error_msg = str(e).lower()
                sender_test_results.append({
                    'sender': sender,
                    'error': str(e),
                    'success': False
                })
                
                # Analyze specific error types
                if '403' in error_msg or 'forbidden' in error_msg:
                    results['recommendations'].append({
                        'priority': 'critical',
                        'issue': 'Sender email not verified',
                        'solution': f'Verify sender domain or email "{sender}" in SendGrid Dashboard > Settings > Sender Authentication'
                    })
                elif '401' in error_msg or 'unauthorized' in error_msg:
                    results['recommendations'].append({
                        'priority': 'critical',
                        'issue': 'API key lacks Mail Send permissions',
                        'solution': 'Go to SendGrid Dashboard > Settings > API Keys and ensure "Mail Send" permission is enabled'
                    })
        
        results['sender_verification'] = sender_test_results
        
        # Step 5: Generate specific recommendations based on findings
        if not any(test['success'] for test in sender_test_results if 'success' in test):
            results['recommendations'].append({
                'priority': 'critical',
                'issue': 'No working sender email found',
                'solution': 'Set up sender authentication in SendGrid: Dashboard > Settings > Sender Authentication > Verify a Single Sender'
            })
        
        # Add general setup recommendations
        results['recommendations'].append({
            'priority': 'medium',
            'issue': 'SendGrid setup verification',
            'solution': 'Complete SendGrid setup: 1) Verify sender email, 2) Enable Mail Send API permissions, 3) Test with verified sender'
        })
        
    except ImportError:
        results['recommendations'].append({
            'priority': 'high',
            'issue': 'SendGrid library not installed',
            'solution': 'Install SendGrid: pip install sendgrid'
        })
    except Exception as e:
        results['recommendations'].append({
            'priority': 'high',
            'issue': f'Diagnostic failed: {str(e)}',
            'solution': 'Check SendGrid configuration and try again'
        })
    
    return results

def print_diagnostic_report():
    """Print a formatted diagnostic report"""
    print("\n" + "="*60)
    print("FIELDVISION AI - EMAIL DIAGNOSTIC REPORT")
    print("="*60)
    
    results = run_comprehensive_email_diagnostics()
    
    # Configuration Status
    print(f"\n📧 SendGrid Configuration:")
    print(f"  API Key Configured: {'✅' if results['sendgrid_configured'] else '❌'}")
    print(f"  API Key Valid: {'✅' if results['api_key_valid'] else '❌'}")
    print(f"  Permissions Check: {results['permissions_check'] or '❌'}")
    
    # Sender Verification Results
    if results['sender_verification']:
        print(f"\n📮 Sender Verification Tests:")
        for test in results['sender_verification']:
            status = "✅" if test.get('success') else "❌"
            print(f"  {status} {test['sender']}")
            if 'error' in test:
                print(f"      Error: {test['error'][:100]}...")
    
    # Recommendations
    if results['recommendations']:
        print(f"\n🔧 RECOMMENDED ACTIONS:")
        for i, rec in enumerate(results['recommendations'], 1):
            priority_icon = "🚨" if rec['priority'] == 'critical' else "⚠️" if rec['priority'] == 'high' else "💡"
            print(f"\n  {i}. {priority_icon} {rec['issue']}")
            print(f"     Solution: {rec['solution']}")
    
    print(f"\n" + "="*60)
    return results

if __name__ == "__main__":
    print_diagnostic_report()